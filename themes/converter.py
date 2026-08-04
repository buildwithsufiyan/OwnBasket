import logging
import os
import re
import shutil
from pathlib import Path

from bs4 import BeautifulSoup
from django.conf import settings
from django.db import transaction

from .models import TemplateConversionLog, Theme, ThemeFileBackup

logger = logging.getLogger(__name__)

# Simple price pattern. A more robust one would handle various currencies and formats.
PRICE_PATTERN = re.compile(r"(\$|€|£|₹)\s?(\d{1,3}(,\d{3})*|\d+)(\.\d{1,2})?")


def backup_file(file_path: Path):
    """Create a backup of the original file before modifying."""
    backup_dir = file_path.parent / ".backups"
    backup_dir.mkdir(exist_ok=True)

    version = 1
    while (backup_dir / f"{file_path.stem}.v{version}{file_path.suffix}").exists():
        version += 1

    backup_path = backup_dir / f"{file_path.stem}.v{version}{file_path.suffix}"
    shutil.copy(file_path, backup_path)
    logger.info(f"Created backup for {file_path.name} at {backup_path}")
    return backup_path, version


def get_unique_selector(tag):
    """
    Generates a unique CSS selector for a BeautifulSoup tag.
    """
    if not tag:
        return None

    path = []
    while tag and tag.name != "[document]":
        selector = tag.name
        if tag.get("id"):
            selector = f"#{tag['id']}"
            path.insert(0, selector)
            break  # ID is unique, no need to go further

        if tag.get("class"):
            classes = ".".join(tag["class"])
            selector += f".{classes}"

        # Find position among siblings with the same tag name
        siblings = tag.find_previous_siblings(tag.name)
        position = len(siblings) + 1
        selector += f":nth-of-type({position})"

        path.insert(0, selector)
        tag = tag.parent

    return " > ".join(path)


def apply_suggestion_to_file(suggestion: TemplateConversionLog):
    """
    Applies a single suggestion to its corresponding file using DOM manipulation.
    """
    theme_dir = settings.BASE_DIR / "themes" / suggestion.theme.theme_folder
    file_path = (theme_dir / suggestion.file_path).resolve()

    if not file_path.is_file():
        raise FileNotFoundError(f"Template file not found: {file_path}")

    # 1. Create a versioned backup
    backup_path, version = backup_file(file_path)
    ThemeFileBackup.objects.create(
        theme=suggestion.theme,
        file_path=suggestion.file_path,
        version=version,
        backup_file_path=str(backup_path.relative_to(settings.BASE_DIR)),
    )

    # 2. Read, parse, and modify
    with file_path.open("r+", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

        # 3. Find the target element
        target_element = soup.select_one(suggestion.target_selector)

        if not target_element:
            raise ValueError(
                "Conflict: Target element not found. The template may have changed."
            )

        # 4. Conflict detection
        if str(target_element.prettify()).strip() != suggestion.original_html.strip():
            logger.warning(
                f"Conflict detected for suggestion {suggestion.id}. Original HTML has changed."
            )
            # We can still proceed, but this is a sign of potential issues.

        # 5. Apply the change
        # For now, we handle simple VAR replacement. LOOP is more complex.
        if suggestion.conversion_type == TemplateConversionLog.ConversionType.VAR.value:
            new_tag = BeautifulSoup(suggestion.suggested_code, "html.parser")
            target_element.replace_with(new_tag)
        elif (
            suggestion.conversion_type
            == TemplateConversionLog.ConversionType.WRAP.value
        ):
            # This is a complex operation for wrapping a list of items in a for loop.
            # The target_element is the parent container.

            # Find the first child that is likely the repeating item
            first_item = target_element.find(recursive=False)
            if not first_item:
                raise ValueError("Cannot apply loop: wrapper element has no children.")

            # Get all siblings with the same class structure
            repeating_items = target_element.find_all(
                class_=first_item.get("class"), recursive=False
            )

            # Keep only the first item, remove the rest
            for item in repeating_items[1:]:
                item.decompose()

            # Wrap the remaining item with the for loop
            first_item.wrap(
                soup.new_tag(
                    "div", attrs={"__dj-loop-start": "{% for product in products %}"}
                )
            )
            first_item.insert_after(
                soup.new_tag("div", attrs={"__dj-loop-end": "{% endfor %}"})
            )

        else:
            raise NotImplementedError(
                f"Conversion type '{suggestion.conversion_type}' not yet implemented for auto-apply."
            )

        # 6. Write back to file
        f.seek(0)
        # Replace our temporary tags with actual Django template tags
        final_html = str(soup)
        final_html = final_html.replace(
            '<div __dj-loop-start="{% for product in products %}"></div>',
            "{% for product in products %}",
        )
        final_html = final_html.replace(
            '<div __dj-loop-end="{% endfor %}"></div>', "{% endfor %}"
        )

        f.write(final_html)
        f.truncate()

    return True


@transaction.atomic
def analyze_html_file(theme: Theme, file_path: Path):
    """
    Analyzes a single HTML file for potential conversions.
    This is a heuristic-based, non-destructive analysis. It only creates suggestions.
    """
    logger.info(f"Analyzing {file_path} for theme '{theme.name}'")
    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
    except Exception as e:
        logger.warning("Could not read or parse %s", file_path, exc_info=e)
        return

    # Clear old pending suggestions for this file
    TemplateConversionLog.objects.filter(
        theme=theme,
        file_path=str(
            file_path.relative_to(settings.BASE_DIR / "themes" / theme.theme_folder)
        ),
        status=TemplateConversionLog.Status.PENDING,
    ).delete()

    # --- Find potential product prices ---
    # Find text nodes that match the price pattern
    price_texts = soup.find_all(string=PRICE_PATTERN)
    for text_node in price_texts:
        # Avoid converting prices inside scripts or styles
        if text_node.parent.name in ["script", "style"]:
            continue

        # High confidence: price is inside a tag with class 'price' or 'amount'
        parent_classes = text_node.parent.get("class", [])
        confidence = 0.6
        if any(c in ["price", "amount", "cost"] for c in parent_classes):
            confidence = 0.9

        target_element = text_node.parent
        selector = get_unique_selector(target_element)
        if not selector:
            continue

        TemplateConversionLog.objects.create(
            theme=theme,
            file_path=str(
                file_path.relative_to(settings.BASE_DIR / "themes" / theme.theme_folder)
            ),
            line_number=target_element.sourceline,
            target_selector=selector,
            status=TemplateConversionLog.Status.PENDING,
            conversion_type=TemplateConversionLog.ConversionType.VAR,
            original_html=str(target_element.prettify()),
            suggested_code=str(
                target_element.replace(text_node, "{{ product.price|currency }}")
            ),
            confidence=confidence,
            description="Detected a potential product price. Suggest replacing with a dynamic price variable.",
        )

    # --- Find potential product grids (loops) ---
    # Look for repeated class names at the same level
    class_counts = {}
    for tag in soup.find_all(class_=True):
        # Simple heuristic: look for elements with siblings having the exact same class list
        if not tag.get("class"):
            continue
        class_tuple = tuple(sorted(tag.get("class")))

        next_sibling = tag.find_next_sibling(class_=tag.get("class"))
        if next_sibling:
            class_counts[class_tuple] = class_counts.get(class_tuple, 0) + 1

    for classes, count in class_counts.items():
        if count > 2:  # If we find more than 2 repeating items, it's likely a list
            first_item = soup.find(class_=classes)
            if not first_item:
                continue

            wrapper_element = first_item.parent
            selector = get_unique_selector(wrapper_element)
            if not selector:
                continue

            TemplateConversionLog.objects.create(
                theme=theme,
                file_path=str(
                    file_path.relative_to(
                        settings.BASE_DIR / "themes" / theme.theme_folder
                    )
                ),
                line_number=wrapper_element.sourceline,
                target_selector=selector,
                status=TemplateConversionLog.Status.PENDING,
                conversion_type=TemplateConversionLog.ConversionType.WRAP,
                original_html=str(
                    wrapper_element.prettify(limit=20)
                ),  # Show the container
                suggested_code="{% for product in products %} ... {% endfor %}",
                confidence=0.75,
                description=f"Detected a potential product grid with {count+1} items (class: .{'.'.join(classes)}). Suggest wrapping in a for loop.",
            )
            # Break after finding one potential loop to avoid spamming suggestions
            break


def run_template_conversion(theme: Theme):
    """
    Main entry point for the conversion process for a given theme.
    """
    theme_dir = settings.BASE_DIR / "themes" / theme.theme_folder
    if not theme_dir.is_dir():
        logger.error(f"Theme directory not found for conversion: {theme_dir}")
        return

    for html_file in theme_dir.glob("*.html"):
        analyze_html_file(theme, html_file)
