import io
import json
import os
import shutil
import zipfile
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils.text import slugify
from django.conf import settings, global_settings
from django.utils._os import safe_join
from .converter import run_template_conversion, apply_suggestion_to_file
from .models import (
    Theme,
    HEADER_CHOICES,
    HERO_CHOICES,
    CATEGORY_CHOICES,
    BRAND_CHOICES,
    PRODUCT_CARD_CHOICES,
    PRODUCT_DETAIL_CHOICES,
    CART_CHOICES,
    CHECKOUT_CHOICES,
    ThemeFileBackup,
    TemplateConversionLog,
    FOOTER_CHOICES,
    FONT_CHOICES,
    BORDER_RADIUS_CHOICES,
    BUTTON_STYLE_CHOICES,
    ANIMATION_CHOICES,
)
from .services import get_theme_validation_map, scan_theme_packages, install_theme_zip


@staff_member_required
def theme_manager(request):
    validation_map = get_theme_validation_map()
    themes = Theme.objects.all().order_by("-is_active", "-created_at")
    for theme in themes:
        validation = validation_map.get(theme.theme_folder)
        theme.scan_errors = validation.errors if validation else []
        theme.scan_warnings = validation.warnings if validation else []

    preview_theme_id = request.session.get("preview_theme_id")
    preview_theme = None
    if preview_theme_id:
        preview_theme = Theme.objects.filter(pk=preview_theme_id).first()

    return render(
        request,
        "themes/manager.html",
        {
            "themes": themes,
            "preview_theme": preview_theme,
            "validation_map": validation_map,
        },
    )


@staff_member_required
@require_POST
def scan_themes(request):
    results = scan_theme_packages()
    created_count = sum(1 for result in results if result.created)
    updated_count = sum(1 for result in results if result.updated and not result.errors)
    invalid_results = [result for result in results if result.errors]

    if created_count or updated_count:
        messages.success(
            request,
            f"Theme scan complete. Added {created_count}, updated {updated_count}.",
        )
    else:
        messages.info(request, "Theme scan complete. No new valid themes found.")

    for result in invalid_results:
        messages.error(request, f"{result.folder_name}: " + " ".join(result.errors))

    return redirect("themes:theme_manager")


@staff_member_required
def apply_theme(request, theme_id):
    theme = get_object_or_404(Theme, pk=theme_id)
    validation = get_theme_validation_map().get(theme.theme_folder)
    if validation and validation.errors:
        messages.error(
            request,
            f"Theme '{theme.name}' cannot be activated until validation errors are fixed.",
        )
        return redirect("themes:theme_manager")

    theme.is_active = True
    theme.save()

    # Clear preview session when applying
    if "preview_theme_id" in request.session:
        del request.session["preview_theme_id"]

    messages.success(request, f"Theme '{theme.name}' applied successfully!")
    return redirect("themes:theme_manager")


@staff_member_required
def preview_theme(request, theme_id):
    theme = get_object_or_404(Theme, pk=theme_id)
    request.session["preview_theme_id"] = theme.id
    messages.success(
        request,
        f"Temporary Preview mode activated for '{theme.name}'. Visit the storefront to test.",
    )
    return redirect("themes:theme_manager")


@staff_member_required
def preview_clear(request):
    if "preview_theme_id" in request.session:
        del request.session["preview_theme_id"]
    messages.info(
        request, "Preview cleared. Storefront returned to active theme design."
    )
    return redirect("themes:theme_manager")


@staff_member_required
def delete_theme(request, theme_id):
    theme = get_object_or_404(Theme, pk=theme_id)
    if theme.is_active:
        messages.error(
            request, "Cannot delete the active theme. Apply another theme first."
        )
        return redirect("themes:theme_manager")

    slug = theme.slug
    # Clean up static and template files if they exist
    templates_path = os.path.join(settings.BASE_DIR, "templates", "themes", slug)
    static_path = os.path.join(settings.BASE_DIR, "static", "themes", slug)

    if os.path.exists(templates_path):
        shutil.rmtree(templates_path, ignore_errors=True)
    if os.path.exists(static_path):
        shutil.rmtree(static_path, ignore_errors=True)

    theme.delete()
    messages.success(request, f"Theme '{theme.name}' deleted successfully.")
    return redirect("themes:theme_manager")


@staff_member_required
def theme_builder(request):
    if request.method == "POST":
        name = request.POST.get("name")
        if not name:
            messages.error(request, "Theme Name is required.")
            return redirect("themes:theme_builder")

        theme = Theme(
            name=name,
            theme_folder=slugify(name),
            is_custom=True,
            header_layout=request.POST.get("header", "header1"),
            hero_layout=request.POST.get("hero", "hero1"),
            category_layout=request.POST.get("category", "layout1"),
            brand_layout=request.POST.get("brand", "layout1"),
            product_card_layout=request.POST.get("product_card", "card1"),
            product_detail_layout=request.POST.get("product_detail", "layout1"),
            cart_layout=request.POST.get("cart", "layout1"),
            checkout_layout=request.POST.get("checkout", "layout1"),
            footer_layout=request.POST.get("footer", "footer1"),
            font_family=request.POST.get("font_family", "Inter"),
            border_radius=request.POST.get("border_radius", "10px"),
            button_style=request.POST.get("button_style", "rounded"),
            animation_style=request.POST.get("animation_style", "none"),
            primary_color=request.POST.get("primary_color", "#ffb800"),
            secondary_color=request.POST.get("secondary_color", "#232f3e"),
            accent_color=request.POST.get("accent_color", "#ffb800"),
            bg_color=request.POST.get("bg_color", "#f4f6f9"),
            text_color=request.POST.get("text_color", "#1a1a1a"),
            border_color=request.POST.get("border_color", "#eaecf0"),
            button_color=request.POST.get("button_color", "#ffb800"),
            hover_color=request.POST.get("hover_color", "#e0a200"),
        )
        theme.save()
        messages.success(request, f"Custom theme '{theme.name}' built successfully!")
        return redirect("themes:theme_manager")

    return render(
        request,
        "themes/builder.html",
        {
            "headers": HEADER_CHOICES,
            "heroes": HERO_CHOICES,
            "categories": CATEGORY_CHOICES,
            "brands": BRAND_CHOICES,
            "product_cards": PRODUCT_CARD_CHOICES,
            "product_details": PRODUCT_DETAIL_CHOICES,
            "carts": CART_CHOICES,
            "checkouts": CHECKOUT_CHOICES,
            "footers": FOOTER_CHOICES,
            "fonts": FONT_CHOICES,
            "border_radii": BORDER_RADIUS_CHOICES,
            "button_styles": BUTTON_STYLE_CHOICES,
            "animations": ANIMATION_CHOICES,
        },
    )


@staff_member_required
def theme_settings(request):
    active_theme = Theme.objects.filter(is_active=True).first()
    if not active_theme:
        messages.warning(
            request, "No active theme selected. Build or select a theme first."
        )
        return redirect("themes:theme_manager")

    if request.method == "POST":
        active_theme.primary_color = request.POST.get("primary_color")
        active_theme.secondary_color = request.POST.get("secondary_color")
        active_theme.accent_color = request.POST.get("accent_color")
        active_theme.bg_color = request.POST.get("bg_color")
        active_theme.text_color = request.POST.get("text_color")
        active_theme.border_color = request.POST.get("border_color")
        active_theme.button_color = request.POST.get("button_color")
        active_theme.hover_color = request.POST.get("hover_color")

        active_theme.font_family = request.POST.get("font_family")
        active_theme.border_radius = request.POST.get("border_radius")
        active_theme.button_style = request.POST.get("button_style")
        active_theme.animation_style = request.POST.get("animation_style")

        active_theme.save()
        messages.success(request, "Theme settings saved successfully!")
        return redirect("themes:theme_manager")

    return render(
        request,
        "themes/settings.html",
        {
            "theme": active_theme,
            "fonts": FONT_CHOICES,
            "border_radii": BORDER_RADIUS_CHOICES,
            "button_styles": BUTTON_STYLE_CHOICES,
            "animations": ANIMATION_CHOICES,
        },
    )


@staff_member_required
def import_theme(request):
    if request.method == "POST" and request.FILES.get("theme_file"):
        uploaded_file = request.FILES["theme_file"]
        result = install_theme_zip(uploaded_file)

        if result.is_valid:
            messages.success(
                request, f"Theme '{result.theme.name}' was installed successfully!"
            )
            for warning in result.warnings:
                messages.warning(request, warning)

            # --- PHASE 3 CHANGE: Redirect to mapping page for static themes ---
            if result.is_static_import:
                messages.info(
                    request,
                    "Theme installed. Please map your HTML files to the required page types.",
                )
                return redirect("themes:template_mapping", theme_id=result.theme.id)

            # --- Original redirection for OwnBasket themes ---
            if TemplateConversionLog.objects.filter(
                theme=result.theme, status="PENDING"
            ).exists():
                messages.info(
                    request, "New conversion suggestions are available for review."
                )
                return redirect(
                    "themes:template_converter_review", theme_id=result.theme.id
                )

            return redirect("themes:theme_manager")
        else:
            for error in result.errors:
                messages.error(request, error)
            # Redirect back to the import page to show errors
            return redirect("themes:import_theme")

    return render(request, "themes/import.html")


OWNBASKET_TEMPLATE_TYPES = {
    "home": {"name": "Home Page", "keywords": ["index", "home"]},
    "product_list": {
        "name": "Product Listing",
        "keywords": ["product", "shop", "listing", "grid"],
    },
    "product_detail": {
        "name": "Product Detail",
        "keywords": ["detail", "item", "single-product"],
    },
    "category_list": {
        "name": "Category Listing",
        "keywords": ["category", "categories"],
    },
    "cart": {"name": "Cart Page", "keywords": ["cart", "basket", "bag"]},
    "checkout": {"name": "Checkout Page", "keywords": ["checkout", "buy", "purchase"]},
    "wishlist": {"name": "Wishlist", "keywords": ["wishlist", "wish", "favorite"]},
    "account": {
        "name": "My Account",
        "keywords": ["account", "profile", "dashboard", "user"],
    },
    "login": {
        "name": "Login/Register",
        "keywords": ["login", "register", "signin", "signup"],
    },
    "contact": {"name": "Contact Page", "keywords": ["contact"]},
    "blog_list": {"name": "Blog Listing", "keywords": ["blog"]},
    "blog_detail": {"name": "Blog Post Detail", "keywords": ["post", "article"]},
    "search_results": {"name": "Search Results", "keywords": ["search"]},
}


def _suggest_mapping(filename, page_types):
    """Intelligently suggest a page type for a given filename."""
    filename_base = os.path.splitext(filename.lower())[0]
    for type_key, type_info in page_types.items():
        for keyword in type_info["keywords"]:
            if keyword in filename_base:
                return type_key
    return None


@staff_member_required
def template_mapping(request, theme_id):
    theme = get_object_or_404(Theme, pk=theme_id)
    theme_dir = settings.BASE_DIR / "themes" / theme.theme_folder

    html_files = sorted([f.name for f in theme_dir.glob("*.html")])

    if request.method == "POST":
        mappings = {}
        for page_type in OWNBASKET_TEMPLATE_TYPES:
            selected_file = request.POST.get(f"mapping_{page_type}")
            if selected_file:
                mappings[page_type] = selected_file

        theme.template_mappings = mappings
        theme.save()
        messages.success(
            request, f"Template mappings for '{theme.name}' saved successfully."
        )
        return redirect("themes:theme_manager")

    # Auto-suggest mappings if none exist
    current_mappings = theme.template_mappings or {}
    if not current_mappings and html_files:
        suggested_mappings = {}
        # Reverse mapping to avoid assigning one file to multiple types
        file_to_type_map = {}
        for html_file in html_files:
            suggestion = _suggest_mapping(html_file, OWNBASKET_TEMPLATE_TYPES)
            if suggestion and suggestion not in suggested_mappings:
                suggested_mappings[suggestion] = html_file
        current_mappings = suggested_mappings

    return render(
        request,
        "themes/mapping.html",
        {
            "theme": theme,
            "html_files": html_files,
            "page_types": OWNBASKET_TEMPLATE_TYPES,
            "current_mappings": current_mappings,
        },
    )


@staff_member_required
def template_converter_review(request, theme_id):
    theme = get_object_or_404(Theme, pk=theme_id)
    pending_suggestions = TemplateConversionLog.objects.filter(
        theme=theme, status=TemplateConversionLog.Status.PENDING
    )

    return render(
        request,
        "themes/converter_review.html",
        {
            "theme": theme,
            "suggestions": pending_suggestions,
        },
    )


@staff_member_required
@require_POST
def apply_suggestion(request, log_id):
    action = request.POST.get("action")
    suggestion_ids = request.POST.getlist("suggestions")

    if not suggestion_ids:
        messages.error(request, "Please select at least one suggestion.")
        # We need theme_id to redirect back, let's try to get it from a log_id if available
        if log_id != 0:
            theme_id = get_object_or_404(TemplateConversionLog, pk=log_id).theme.id
            return redirect("themes:template_converter_review", theme_id=theme_id)
        return redirect("themes:theme_manager")  # Fallback

    suggestions = TemplateConversionLog.objects.filter(id__in=suggestion_ids)
    theme_id = suggestions.first().theme.id

    for suggestion in suggestions:
        if action == "apply":
            try:
                apply_suggestion_to_file(suggestion)
                suggestion.status = TemplateConversionLog.Status.APPLIED
                suggestion.save()
                messages.success(
                    request,
                    f"Successfully applied suggestion for {suggestion.file_path}.",
                )
            except (FileNotFoundError, ValueError, NotImplementedError) as e:
                messages.error(
                    request,
                    f"Could not apply suggestion for {suggestion.file_path}: {e}",
                )
            except Exception as e:
                messages.error(
                    request,
                    f"An unexpected error occurred for {suggestion.file_path}: {e}",
                )

        elif action == "reject":
            suggestion.status = TemplateConversionLog.Status.REJECTED
            suggestion.save()
            messages.warning(
                request, f"Suggestion for {suggestion.file_path} was rejected."
            )

    return redirect("themes:template_converter_review", theme_id=theme_id)


@staff_member_required
def file_history(request, theme_id):
    theme = get_object_or_404(Theme, pk=theme_id)
    backups = ThemeFileBackup.objects.filter(theme=theme).order_by(
        "file_path", "-version"
    )

    # Group backups by file path
    history = {}
    for backup in backups:
        if backup.file_path not in history:
            history[backup.file_path] = []
        history[backup.file_path].append(backup)

    return render(
        request,
        "themes/history.html",
        {
            "theme": theme,
            "history": history,
        },
    )


@staff_member_required
@require_POST
def restore_backup(request, backup_id):
    backup_to_restore = get_object_or_404(ThemeFileBackup, pk=backup_id)
    theme = backup_to_restore.theme

    theme_dir = settings.BASE_DIR / "themes" / theme.theme_folder
    current_file_path = (theme_dir / backup_to_restore.file_path).resolve()
    backup_file_path = (
        settings.BASE_DIR / backup_to_restore.backup_file_path
    ).resolve()

    if not backup_file_path.exists():
        messages.error(request, f"Backup file not found: {backup_file_path}")
        return redirect("themes:file_history", theme_id=theme.id)

    try:
        # First, create a new backup of the current state before overwriting it
        from .converter import backup_file

        new_backup_path, new_version = backup_file(current_file_path)
        ThemeFileBackup.objects.create(
            theme=theme,
            file_path=backup_to_restore.file_path,
            version=new_version,
            backup_file_path=str(new_backup_path.relative_to(settings.BASE_DIR)),
            restored_from=backup_to_restore,
        )

        # Now, restore the old version
        shutil.copy(backup_file_path, current_file_path)
        messages.success(
            request,
            f"Successfully restored '{backup_to_restore.file_path}' to version {backup_to_restore.version}.",
        )
    except Exception as e:
        messages.error(request, f"An error occurred during restore: {e}")

    return redirect("themes:file_history", theme_id=theme.id)


@staff_member_required
def export_theme(request, theme_id):
    theme = get_object_or_404(Theme, pk=theme_id)
    slug = theme.slug

    # Generate JSON config
    theme_data = {
        "name": theme.name,
        "version": theme.version,
        "author": theme.author,
        "description": theme.description,
        "header": theme.header_layout,
        "hero": theme.hero_layout,
        "category": theme.category_layout,
        "brand": theme.brand_layout,
        "product_card": theme.product_card_layout,
        "product_detail": theme.product_detail_layout,
        "cart": theme.cart_layout,
        "checkout": theme.checkout_layout,
        "footer": theme.footer_layout,
        "primary_color": theme.primary_color,
        "secondary_color": theme.secondary_color,
        "accent_color": theme.accent_color,
        "bg_color": theme.bg_color,
        "text_color": theme.text_color,
        "border_color": theme.border_color,
        "button_color": theme.button_color,
        "hover_color": theme.hover_color,
        "font_family": theme.font_family,
        "border_radius": theme.border_radius,
        "button_style": theme.button_style,
        "animation_style": theme.animation_style,
    }

    # Create ZIP archive in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Write theme.json
        zip_file.writestr("theme.json", json.dumps(theme_data, indent=4))

        # Write preview image if exists
        if theme.preview_image and os.path.exists(theme.preview_image.path):
            zip_file.write(theme.preview_image.path, "preview.png")

        # Copy custom/imported template files if they exist
        templates_path = os.path.join(settings.BASE_DIR, "templates", "themes", slug)
        if os.path.exists(templates_path):
            for root, _, files in os.walk(templates_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.join(
                        "templates", os.path.relpath(file_path, templates_path)
                    )
                    zip_file.write(file_path, arc_name)

        # Copy custom/imported static files if they exist
        static_path = os.path.join(settings.BASE_DIR, "static", "themes", slug)
        if os.path.exists(static_path):
            for root, _, files in os.walk(static_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.join(
                        "static", os.path.relpath(file_path, static_path)
                    )
                    zip_file.write(file_path, arc_name)

    zip_buffer.seek(0)
    response = FileResponse(zip_buffer, as_attachment=True, filename=f"{slug}.obtheme")
    return response


def theme_asset(request, theme_folder, asset_path):
    base_path = settings.BASE_DIR / "themes" / theme_folder / "static"
    try:
        resolved_path = safe_join(base_path, asset_path)
    except ValueError as exc:
        raise Http404("Theme asset not found.") from exc

    if not os.path.isfile(resolved_path):
        raise Http404("Theme asset not found.")

    return FileResponse(open(resolved_path, "rb"))
