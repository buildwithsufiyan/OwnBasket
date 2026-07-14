from django import template
from django.template.loader import get_template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from themes.services import get_theme_static_url

register = template.Library()


def render_component(context, component_name, **kwargs):
    """
    Renders a layout component using the LayoutResolver from the context.
    This ensures that template resolution is centralized and consistent.
    """
    resolver = context.get("layout_resolver")
    if not resolver:
        # This might happen if the context processor is not active.
        # Fallback to a safe default to avoid breaking the page.
        # A warning could be logged here in a real-world scenario.
        return ""

    # The modern resolver handles all the logic for finding the correct template
    # including fallbacks to the default theme.
    template_path = resolver.get_template_path(component_name)

    # Pass all keyword arguments from the tag directly into the template context.
    # This is used for tags like render_product_card that pass extra data.
    ctx = context.flatten()
    ctx.update(kwargs)

    return render_to_string(template_path, ctx, request=context.request)


@register.simple_tag(takes_context=True)
def theme_static(context, asset_path):
    return get_theme_static_url(context.get("active_theme"), asset_path)


@register.simple_tag(takes_context=True)
def theme_styles(context):
    theme = context.get("active_theme")
    if not theme:
        return ""

    is_dict = isinstance(theme, dict)

    def get_val(key, default):
        if is_dict:
            return theme.get(key, default)
        return getattr(theme, key, default)

    # --- Colors ---
    brand_primary = get_val("brand_primary_color", "#ffb800")
    brand_secondary = get_val("brand_secondary_color", "#232f3e")
    brand_accent = get_val("brand_accent_color", "#ffb800")
    bg_body = get_val("bg_body_color", "#f4f6f9")
    bg_section = get_val("bg_section_color", "#ffffff")
    bg_card = get_val("bg_card_color", "#ffffff")
    bg_header = get_val("bg_header_color", "#ffffff")
    bg_footer = get_val("bg_footer_color", "#232f3e")
    text_primary = get_val("text_primary_color", "#1a1a1a")
    text_secondary = get_val("text_secondary_color", "#6c757d")
    text_heading = get_val("text_heading_color", "#212529")
    text_link = get_val("text_link_color", "#ffb800")
    text_link_hover = get_val("text_link_hover_color", "#e0a200")
    btn_primary_bg = get_val("btn_primary_bg_color", "#ffb800")
    btn_primary_hover_bg = get_val("btn_primary_hover_bg_color", "#e0a200")
    btn_secondary_bg = get_val("btn_secondary_bg_color", "#343a40")
    btn_secondary_hover_bg = get_val("btn_secondary_hover_bg_color", "#232f3e")
    prod_price = get_val("product_price_color", "#d92d20")
    prod_sale_price = get_val("product_sale_price_color", "#d92d20")
    prod_badge_bg = get_val("product_discount_badge_bg_color", "#d92d20")
    prod_badge_text = get_val("product_discount_badge_text_color", "#ffffff")
    status_success = get_val("status_success_color", "#039855")
    status_warning = get_val("status_warning_color", "#f79009")
    status_danger = get_val("status_danger_color", "#d92d20")
    status_info = get_val("status_info_color", "#007bff")
    border_global = get_val("border_global_color", "#eaecf0")
    border_input = get_val("border_input_color", "#ced4da")
    border_card = get_val("border_card_color", "#eaecf0")

    # --- Component Styles ---
    btn_br = f"{get_val('btn_border_radius', 8)}px"
    btn_pad = get_val("btn_padding", "12px 20px")
    btn_fs = f"{get_val('btn_font_size', 16)}px"
    btn_fw = get_val("btn_font_weight", 700)
    btn_bw = f"{get_val('btn_border_width', 1)}px"
    btn_bs = get_val("btn_border_style", "solid")
    btn_hover_anim = get_val("btn_hover_animation", "translateY")
    btn_hover_scale = get_val("btn_hover_scale", 1.05)
    btn_hover_shadow = get_val("btn_hover_shadow", "0 8px 24px rgba(0, 0, 0, 0.1)")

    card_br = f"{get_val('card_border_radius', 12)}px"
    card_bw = f"{get_val('card_border_width', 1)}px"
    card_shadow = get_val("card_box_shadow", "0 8px 24px rgba(0, 0, 0, 0.06)")
    card_hover_shadow = get_val("card_hover_shadow", "0 14px 30px rgba(0, 0, 0, 0.08)")
    card_hover_lift = get_val("card_hover_lift_effect", True)
    card_img_br = f"{get_val('card_image_radius', 0)}px"

    form_input_h = f"{get_val('form_input_height', 46)}px"
    form_input_br = f"{get_val('form_input_border_radius', 8)}px"
    form_input_bw = f"{get_val('form_input_border_width', 1)}px"
    form_input_focus = get_val("form_input_focus_color", "#ffb800")
    form_placeholder = get_val("form_placeholder_color", "#6c757d")

    badge_r = f"{get_val('badge_radius', 999)}px"
    badge_pad = get_val("badge_padding", "6px 12px")
    badge_fs = f"{get_val('badge_font_size', 11)}px"

    alert_r = f"{get_val('alert_radius', 8)}px"
    alert_shadow = get_val("alert_shadow", "0 4px 12px rgba(0, 0, 0, 0.08)")
    alert_pad = get_val("alert_padding", "1rem")

    modal_r = f"{get_val('modal_radius', 16)}px"
    modal_shadow = get_val("modal_shadow", "0 14px 40px rgba(0, 0, 0, 0.15)")

    # --- Legacy & Other Styles ---
    font = get_val("font_family", "Inter")
    radius = get_val("border_radius", "10px")
    btn_style = get_val("button_style", "rounded")
    anim_style = get_val("animation_style", "none")

    styles = f"""
    <!-- Theme Fonts and Styles -->
    <link href="https://fonts.googleapis.com/css2?family={font.replace(' ', '+')}:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            /* Brand Colors */
            --owncart-brand-primary: {brand_primary};
            --owncart-brand-secondary: {brand_secondary};
            --owncart-brand-accent: {brand_accent};

            /* Background Colors */
            --owncart-bg-body: {bg_body};
            --owncart-bg-section: {bg_section};
            --owncart-bg-card: {bg_card};
            --owncart-bg-header: {bg_header};
            --owncart-bg-footer: {bg_footer};

            /* Text Colors */
            --owncart-text-primary: {text_primary};
            --owncart-text-secondary: {text_secondary};
            --owncart-text-heading: {text_heading};
            --owncart-text-link: {text_link};
            --owncart-text-link-hover: {text_link_hover};

            /* Button Colors */
            --owncart-btn-primary-bg: {btn_primary_bg};
            --owncart-btn-primary-hover-bg: {btn_primary_hover_bg};
            --owncart-btn-secondary-bg: {btn_secondary_bg};
            --owncart-btn-secondary-hover-bg: {btn_secondary_hover_bg};
            
            /* Product Colors */
            --owncart-product-price: {prod_price};
            --owncart-product-sale-price: {prod_sale_price};
            --owncart-product-badge-bg: {prod_badge_bg};
            --owncart-product-badge-text: {prod_badge_text};

            /* Status Colors */
            --owncart-status-success: {status_success};
            --owncart-status-warning: {status_warning};
            --owncart-status-danger: {status_danger};
            --owncart-status-info: {status_info};

            /* Border Colors */
            --owncart-border-global: {border_global};
            --owncart-border-input: {border_input};
            --owncart-border-card: {border_card};

            /* Component Styles: Buttons */
            --owncart-btn-br: {btn_br};
            --owncart-btn-pad: {btn_pad};
            --owncart-btn-fs: {btn_fs};
            --owncart-btn-fw: {btn_fw};
            --owncart-btn-bw: {btn_bw};
            --owncart-btn-bs: {btn_bs};
            --owncart-btn-hover-shadow: {btn_hover_shadow};
            
            /* Component Styles: Cards */
            --owncart-card-br: {card_br};
            --owncart-card-bw: {card_bw};
            --owncart-card-shadow: {card_shadow};
            --owncart-card-hover-shadow: {card_hover_shadow};
            --owncart-card-img-br: {card_img_br};
            
            /* Component Styles: Forms */
            --owncart-form-input-h: {form_input_h};
            --owncart-form-input-br: {form_input_br};
            --owncart-form-input-bw: {form_input_bw};
            --owncart-form-input-focus: {form_input_focus};
            --owncart-form-placeholder: {form_placeholder};
            
            /* Component Styles: Badges */
            --owncart-badge-r: {badge_r};
            --owncart-badge-pad: {badge_pad};
            --owncart-badge-fs: {badge_fs};
            
            /* Component Styles: Alerts */
            --owncart-alert-r: {alert_r};
            --owncart-alert-shadow: {alert_shadow};
            --owncart-alert-pad: {alert_pad};
            
            /* Component Styles: Modal */
            --owncart-modal-r: {modal_r};
            --owncart-modal-shadow: {modal_shadow};

            /* Legacy Aliases (to be deprecated) */
            --owncart-primary: var(--owncart-brand-primary);
            --owncart-primary-hover: var(--owncart-btn-primary-hover-bg);
            --owncart-dark: var(--owncart-brand-secondary);
            --owncart-secondary: var(--owncart-brand-secondary);
            --owncart-bg: var(--owncart-bg-body);
            --owncart-text: var(--owncart-text-primary);
            --owncart-border: var(--owncart-border-global);
            --owncart-accent: var(--owncart-brand-accent);
            --owncart-button: var(--owncart-btn-primary-bg);
            --owncart-button-hover: var(--owncart-btn-primary-hover-bg);
            --owncart-red: var(--owncart-status-danger);
            --owncart-green: var(--owncart-status-success);
            
            /* Static Vars */
            --owncart-muted: #667085;

            --radius-md: {radius};
            --shadow-sm: 0 4px 12px rgba(0, 0, 0, 0.04);
            --shadow-md: 0 8px 24px rgba(0, 0, 0, 0.06);
            --shadow-lg: 0 14px 30px rgba(0, 0, 0, 0.08);

            --section-space-desktop: 80px;
            --section-space-tablet: 60px;
            --section-space-mobile: 40px;
            
            --transition-fast: 0.25s ease;
            --transition-base: 0.3s ease;
        }}
        
        *,
        *::before,
        *::after {{
            box-sizing: border-box;
        }}

        body {{
            font-family: '{font}', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--owncart-bg-body);
            color: var(--owncart-text-primary);
            overflow-x: hidden;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
            line-height: 1.55;
        }}

        h1,
        h2,
        h3,
        h4,
        h5,
        h6 {{
            color: var(--owncart-text-heading);
            font-weight: 700;
            letter-spacing: -0.02em;
        }}

        p,
        li,
        label,
        span,
        small {{
            color: inherit;
        }}

        /* Scrollbar styling */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}

        ::-webkit-scrollbar-track {{
            background: #f1f1f1;
        }}

        ::-webkit-scrollbar-thumb {{
            background: #ccc;
            border-radius: var(--radius-md);
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: #aaa;
        }}

        /* Global style configurations */
        .btn-owncart {{
            background-color: var(--owncart-btn-primary-bg);
            color: var(--owncart-dark);
            font-weight: var(--owncart-btn-fw);
            font-size: var(--owncart-btn-fs);
            border: var(--owncart-btn-bw) var(--owncart-btn-bs) var(--owncart-btn-primary-bg);
            border-radius: var(--owncart-btn-br);
            min-height: var(--owncart-form-input-h);
            padding: var(--owncart-btn-pad);
            transition: transform var(--transition-fast), box-shadow var(--transition-fast), background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast);
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            box-shadow: var(--shadow-sm);
        }}

        .btn-owncart:hover {{
            background-color: var(--owncart-btn-primary-hover-bg);
            color: var(--owncart-dark);
            border-color: var(--owncart-btn-primary-hover-bg);
            transform: translateY(-1px);
            box-shadow: var(--owncart-btn-hover-shadow);
        }}

        .btn-owncart:active {{
            transform: translateY(0);
        }}

        .card-owncart, .product-card {{
            background: var(--owncart-bg-card);
            border: var(--owncart-card-bw) solid var(--owncart-border-card);
            border-radius: var(--owncart-card-br);
            box-shadow: var(--owncart-card-shadow);
            transition: transform var(--transition-base), box-shadow var(--transition-base), border-color var(--transition-base);
            overflow: hidden;
        }}

        .card-owncart:hover, .product-card:hover {{
            transform: {'translateY(-3px)' if card_hover_lift else 'none'};
            box-shadow: var(--owncart-card-hover-shadow);
        }}

        .form-control,
        .form-select {{
            min-height: var(--owncart-form-input-h);
            border: var(--owncart-form-input-bw) solid var(--owncart-border-input);
            border-radius: var(--owncart-form-input-br);
            color: var(--owncart-dark);
            box-shadow: none;
            transition: border-color var(--transition-fast), box-shadow var(--transition-fast), background-color var(--transition-fast);
        }}
        
        .form-control::placeholder {{
            color: var(--owncart-form-placeholder);
            opacity: 1;
        }}

        textarea.form-control {{
            min-height: 120px;
        }}

        .form-control:focus,
        .form-select:focus {{
            border-color: var(--owncart-form-input-focus);
            box-shadow: 0 0 0 3px color-mix(in srgb, var(--owncart-form-input-focus) 20%, transparent);
        }}

        .modal-content {{
            border: 1px solid var(--owncart-border-global);
            border-radius: var(--owncart-modal-r);
            box-shadow: var(--owncart-modal-shadow);
        }}
        
        .alert {{
            border-radius: var(--owncart-alert-r);
            box-shadow: var(--owncart-alert-shadow);
            padding: var(--owncart-alert-pad);
        }}

        .table,
        .accordion-item {{
            border-color: var(--owncart-border-global);
        }}

        .section-shell {{
            padding-block: var(--section-space-desktop);
        }}
    """

    # Finalize and return
    styles += "</style>"
    return mark_safe(styles)


def render_component(
    context, component_name, layout_field_name=None, default_layout=None, **kwargs
):
    resolver = context.get("layout_resolver")
    if resolver:
        template_path = resolver.get_template_path(component_name)
        ctx = context.flatten()
        ctx.update(kwargs)
        # RequestContext exposes ``request`` and safely runs context processors.
        # A plain Context may merely contain a RequestFactory request without
        # authentication middleware, so render it from the flattened context.
        request = getattr(context, 'request', None)
        return render_to_string(template_path, ctx, request=request)

    theme = context.get("active_theme")
    if not theme:
        return ""

    if not layout_field_name:
        return ""

    is_dict = isinstance(theme, dict)
    layout = (
        theme.get(layout_field_name, default_layout)
        if is_dict
        else getattr(theme, layout_field_name, default_layout)
    )
    tpl_path = f"themes/default/{component_name}/{layout}.html"

    # Flatten context to dictionary, rendering with request to preserve session parameters
    ctx = context.flatten()
    ctx.update(kwargs)
    return render_to_string(tpl_path, ctx, request=context.request)


@register.simple_tag(takes_context=True)
def render_header(context):
    return render_component(context, "header", default_layout="header1")


@register.simple_tag(takes_context=True)
def render_hero(context):
    return render_component(context, "hero")


@register.simple_tag(takes_context=True)
def render_categories(context):
    # Note: The component name is 'category' in the registry
    return render_component(context, "category")


@register.simple_tag(takes_context=True)
def render_brands(context):
    # Note: The component name is 'brand' in the registry
    return render_component(context, "brand")


@register.simple_tag(takes_context=True)
def render_footer(context):
    return render_component(context, "footer", default_layout="footer1")


@register.simple_tag(takes_context=True)
def render_product_card(context, product):
    # Note: The component name is 'product_list' in the registry
    return render_component(context, "product_list", product=product)


@register.simple_tag(takes_context=True)
def render_product_detail(context, product, reviews=None):
    return render_component(context, "product_detail", product=product, reviews=reviews)


@register.simple_tag(takes_context=True)
def render_cart(context, cart, cart_items):
    return render_component(context, "cart", cart=cart, cart_items=cart_items)


@register.simple_tag(takes_context=True)
def render_checkout(context, order=None):
    return render_component(context, "checkout", order=order)
