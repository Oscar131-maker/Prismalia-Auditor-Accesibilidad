"""
Mapping of custom WCAG 2.2 audit criteria to pa11y issue codes.
Each criterion has:
  - id: unique slug
  - section: Perceptibilidad | Operabilidad | Comprensibilidad | Robustez
  - label: descripción en español del criterio
  - codes: lista de subcadenas exactas de códigos pa11y que activan este criterio (vacío = solo manual)
  - manual: True si pa11y no puede verificarlo automáticamente
"""

CRITERIA = [
    # ── PERCEPTIBILIDAD ─────────────────────────────────────────────────────
    {
        "id": "img-alt-text",
        "section": "Perceptibilidad",
        "label": "Todas las imágenes tienen texto alternativo (atributo alt)",
        # Pa11y Guideline1_1 cubre imágenes sin alt o con alt inadecuado
        "codes": [
            "WCAG2AA.Principle1.Guideline1_1.1_1_1.H37",   # img sin alt
            "WCAG2AA.Principle1.Guideline1_1.1_1_1.H36",   # img dentro de enlace sin alt
            "WCAG2AA.Principle1.Guideline1_1.1_1_1.H30",   # enlace con solo imagen sin alt
            "Img element is the only content of the link",  # mensaje pa11y htmlcs
        ],
        "manual": False,
    },
    {
        "id": "img-decorative-alt",
        "section": "Perceptibilidad",
        "label": "Imágenes decorativas tienen alt vacío (alt=\"\")",
        "codes": [
            "WCAG2AA.Principle1.Guideline1_1.1_1_1.H67",
            "img-decorative-alt",
        ],
        "manual": False,
    },
    {
        "id": "icon-aria-label",
        "section": "Perceptibilidad",
        "label": "Íconos interactivos tienen title o aria-label descriptivo (menú, subir, WP…)",
        # Solo captura elementos sin nombre accesible que NO son botones de formulario normales
        "codes": [
            "WCAG2AA.Principle1.Guideline1_1.1_1_1.H67",   # img decorativa mal usada en enlace
            "Anchor element found with a valid href attribute, but no link content",
        ],
        "manual": True,
    },
    {
        "id": "logo-home-link",
        "section": "Perceptibilidad",
        "label": "El logotipo tiene un enlace a la página de inicio",
        "codes": ["logo-home-link"],
        "manual": False,
    },
    {
        "id": "img-text-description",
        "section": "Perceptibilidad",
        "label": "Imágenes que contienen texto tienen una descripción textual debajo",
        "codes": ["img-text-description"],
        "manual": False,
    },
    {
        "id": "chart-description",
        "section": "Perceptibilidad",
        "label": "Gráficos, diagramas e infografías tienen descripción accesible",
        "codes": [],
        "manual": True,
    },
    {
        "id": "single-h1",
        "section": "Perceptibilidad",
        "label": "Existe un único encabezado <h1> por página",
        "codes": [
            "WCAG2AA.Principle1.Guideline1_3.1_3_1.G141",
            "single-h1",
        ],
        "manual": False,
    },
    {
        "id": "semantic-headings",
        "section": "Perceptibilidad",
        "label": "Los encabezados usan etiquetas <h1>-<h6>, no <div> o <span>",
        "codes": ["semantic-headings"],
        "manual": False,
    },
    {
        "id": "real-lists",
        "section": "Perceptibilidad",
        "label": "Las listas reales están dentro de <ul>, <ol> y <li>",
        "codes": [
            "WCAG2AA.Principle1.Guideline1_3.1_3_1.H48",
            "real-lists",
        ],
        "manual": False,
    },
    {
        "id": "table-semantics",
        "section": "Perceptibilidad",
        "label": "Las tablas de datos usan <table> con encabezados <th>",
        "codes": [
            "WCAG2AA.Principle1.Guideline1_3.1_3_1.H39",
            "WCAG2AA.Principle1.Guideline1_3.1_3_1.H43",
            "WCAG2AA.Principle1.Guideline1_3.1_3_1.H63",
            "WCAG2AA.Principle1.Guideline1_3.1_3_1.H73",
        ],
        "manual": False,
    },
    {
        "id": "content-without-css",
        "section": "Perceptibilidad",
        "label": "El contenido sigue siendo comprensible sin hojas de estilo CSS",
        "codes": ["content-without-css"],
        "manual": False,
    },
    {
        "id": "orientation",
        "section": "Perceptibilidad",
        "label": "El contenido se puede leer en orientación vertical y horizontal",
        "codes": [
            "WCAG2AA.Principle1.Guideline1_3.1_3_4",
        ],
        "manual": True,
    },
    {
        "id": "no-sensory-only",
        "section": "Perceptibilidad",
        "label": "La información no depende únicamente de posición, forma, tamaño o color",
        "codes": [
            "WCAG2AA.Principle1.Guideline1_3.1_3_3",
            "no-sensory-only",
        ],
        "manual": False,
    },
    {
        "id": "error-not-color-only",
        "section": "Perceptibilidad",
        "label": "Los estados de error, éxito u obligatorio no se indican solo mediante color",
        "codes": [
            "WCAG2AA.Principle1.Guideline1_4.1_4_1",
            "error-not-color-only",
        ],
        "manual": False,
    },
    {
        "id": "color-contrast",
        "section": "Perceptibilidad",
        "label": "Existe contraste de color suficiente en textos, botones y fondos",
        # Pa11y emite 1_4_3 para contraste normal y 1_4_6 para contraste mejorado
        "codes": [
            "WCAG2AA.Principle1.Guideline1_4.1_4_3",
            "WCAG2AA.Principle1.Guideline1_4.1_4_6",
        ],
        "manual": False,
    },
    {
        "id": "zoom-200",
        "section": "Perceptibilidad",
        "label": "El sitio es funcional con zoom al 200% sin pérdida de contenido",
        "codes": [
            "WCAG2AA.Principle1.Guideline1_4.1_4_4",
            "zoom-200",
        ],
        "manual": False,
    },
    {
        "id": "reflow-320",
        "section": "Perceptibilidad",
        "label": "El contenido se adapta a 320px CSS sin scroll horizontal innecesario (reflow)",
        "codes": [
            "WCAG2AA.Principle1.Guideline1_4.1_4_10",
        ],
        "manual": True,
    },
    {
        "id": "hover-focus-visible",
        "section": "Perceptibilidad",
        "label": "El contenido que aparece al pasar el ratón o recibir foco puede cerrarse y mantenerse",
        "codes": [
            "WCAG2AA.Principle1.Guideline1_4.1_4_13",
        ],
        "manual": True,
    },
    {
        "id": "placeholder-no-label",
        "section": "Perceptibilidad",
        "label": "Los placeholders no sustituyen a las etiquetas visibles de formulario",
        "codes": [
            "WCAG2AA.Principle1.Guideline1_3.1_3_1.F68",
            "placeholder-no-label",
        ],
        "manual": False,
    },

    # ── OPERABILIDAD ─────────────────────────────────────────────────────────
    {
        "id": "keyboard-only",
        "section": "Operabilidad",
        "label": "Toda la interfaz es operable únicamente con teclado",
        "codes": [],
        "manual": True,
    },
    {
        "id": "tab-order",
        "section": "Operabilidad",
        "label": "El orden de tabulación sigue una lógica visual y funcional coherente",
        "codes": [
            "WCAG2AA.Principle2.Guideline2_4.2_4_3",
            "tab-order",
        ],
        "manual": False,
    },
    {
        "id": "no-keyboard-trap",
        "section": "Operabilidad",
        "label": "No existen trampas de teclado (el foco no queda atrapado)",
        "codes": [
            "WCAG2AA.Principle2.Guideline2_1.2_1_2",
            "no-keyboard-trap",
        ],
        "manual": False,
    },
    {
        "id": "focusable-interactive",
        "section": "Operabilidad",
        "label": "Todos los elementos interactivos son alcanzables mediante teclado",
        "codes": [
            "WCAG2AA.Principle2.Guideline2_1.2_1_1",
        ],
        "manual": True,
    },
    {
        "id": "focus-visible",
        "section": "Operabilidad",
        "label": "El indicador de foco es visible, consistente y con contraste suficiente",
        "codes": [
            "WCAG2AA.Principle2.Guideline2_4.2_4_7",
            "WCAG2AA.Principle2.Guideline2_4.2_4_11",
            "focus-visible",
        ],
        "manual": False,
    },
    {
        "id": "dropdown-keyboard",
        "section": "Operabilidad",
        "label": "Los menús desplegables son navegables completamente por teclado",
        "codes": [],
        "manual": True,
    },
    {
        "id": "submenu-keyboard",
        "section": "Operabilidad",
        "label": "Los submenús se abren, recorren y cierran por teclado",
        "codes": [],
        "manual": True,
    },
    {
        "id": "accordion-state",
        "section": "Operabilidad",
        "label": "Acordeones, pestañas y desplegables anuncian su estado (expandido/contraído)",
        # Pa11y detecta elementos con rol pero sin aria-expanded cuando corresponde
        "codes": [
            "WCAG2AA.Principle4.Guideline4_1.4_1_2.aria-expanded",
            "accordion-state",
        ],
        "manual": False,
    },
    {
        "id": "carousel-keyboard",
        "section": "Operabilidad",
        "label": "Los carruseles son navegables por teclado",
        "codes": [],
        "manual": True,
    },
    {
        "id": "location-clear",
        "section": "Operabilidad",
        "label": "La ubicación del usuario en el sitio es clara (menú activo, migas de pan…)",
        "codes": [
            "WCAG2AA.Principle2.Guideline2_4.2_4_8",
        ],
        "manual": True,
    },
    {
        "id": "button-accessible-name",
        "section": "Operabilidad",
        "label": "Todos los botones e iconos interactivos tienen nombre accesible",
        # Códigos específicos de pa11y para elementos sin nombre accesible
        "codes": [
            "WCAG2AA.Principle4.Guideline4_1.4_1_2.Button",
            "WCAG2AA.Principle4.Guideline4_1.4_1_2.H91.Button",
            "WCAG2AA.Principle4.Guideline4_1.4_1_2.H91.A.NoContent",
            "This element has role of \"button\" but does not have a name",
            "This element does not have a name available",
        ],
        "manual": False,
    },
    {
        "id": "no-abrupt-change",
        "section": "Operabilidad",
        "label": "Los campos no provocan cambios bruscos de contexto al seleccionar",
        "codes": [
            "WCAG2AA.Principle3.Guideline3_2.3_2_2",
        ],
        "manual": True,
    },
    {
        "id": "sticky-no-block",
        "section": "Operabilidad",
        "label": "Los menús fijos, chats o banners no bloquean la navegación por teclado",
        "codes": ["sticky-no-block"],
        "manual": False,
    },
    {
        "id": "multiple-ways",
        "section": "Operabilidad",
        "label": "Hay más de una forma de localizar contenido (menú, búsqueda, mapa, migas…)",
        "codes": [
            "WCAG2AA.Principle2.Guideline2_4.2_4_5",
        ],
        "manual": True,
    },
    {
        "id": "touch-targets",
        "section": "Operabilidad",
        "label": "Los objetivos táctiles próximos tienen separación suficiente para evitar errores",
        "codes": [
            "WCAG2AA.Principle2.Guideline2_5.2_5_8",
        ],
        "manual": True,
    },

    # ── COMPRENSIBILIDAD ─────────────────────────────────────────────────────
    {
        "id": "lang-attribute",
        "section": "Comprensibilidad",
        "label": "El atributo lang está presente en la etiqueta <html>",
        "codes": [
            "WCAG2AA.Principle3.Guideline3_1.3_1_1.H57.2",
            "WCAG2AA.Principle3.Guideline3_1.3_1_1.H57.3.Lang",
            "WCAG2AA.Principle3.Guideline3_1.3_1_1.H57.3.XmlLang",
            "The html element should have a lang",
            "lang-attr",
        ],
        "manual": False,
    },
    {
        "id": "clear-text",
        "section": "Comprensibilidad",
        "label": "El texto visible es claro y directo, sin jerga innecesaria en acciones clave",
        "codes": [],
        "manual": True,
    },
    {
        "id": "form-instructions",
        "section": "Comprensibilidad",
        "label": "Las instrucciones de formulario son claras antes de que el usuario cometa errores",
        "codes": [],
        "manual": True,
    },
    {
        "id": "required-fields",
        "section": "Comprensibilidad",
        "label": "Los campos obligatorios están identificados de forma visible y programática",
        "codes": [
            "WCAG2AA.Principle3.Guideline3_3.3_3_2",
            "required-fields",
        ],
        "manual": False,
    },
    {
        "id": "visible-label",
        "section": "Comprensibilidad",
        "label": "Cada campo de formulario tiene una etiqueta (<label>) visible y persistente",
        "codes": [
            "WCAG2AA.Principle1.Guideline1_3.1_3_1.F68",
            "WCAG2AA.Principle1.Guideline1_3.1_3_1.H44",
            "WCAG2AA.Principle1.Guideline1_3.1_3_1.H65",
        ],
        "manual": False,
    },
    {
        "id": "field-hints",
        "section": "Comprensibilidad",
        "label": "Las ayudas, ejemplos y formatos esperados aparecen cerca del campo correspondiente",
        "codes": [],
        "manual": True,
    },
    {
        "id": "error-text-not-color",
        "section": "Comprensibilidad",
        "label": "Los errores se muestran en texto, no solo mediante color o iconos",
        "codes": [
            "WCAG2AA.Principle1.Guideline1_4.1_4_1",
        ],
        "manual": True,
    },
    {
        "id": "error-description",
        "section": "Comprensibilidad",
        "label": "Los mensajes de error explican qué ha fallado y cómo corregirlo",
        "codes": [
            "WCAG2AA.Principle3.Guideline3_3.3_3_1",
            "WCAG2AA.Principle3.Guideline3_3.3_3_3",
        ],
        "manual": True,
    },
    {
        "id": "error-programmatic",
        "section": "Comprensibilidad",
        "label": "Los errores están asociados programáticamente al campo correspondiente",
        "codes": [
            "WCAG2AA.Principle3.Guideline3_3.3_3_1",
            "error-programmatic",
        ],
        "manual": False,
    },
    {
        "id": "focus-on-error",
        "section": "Comprensibilidad",
        "label": "Tras enviar un formulario con errores, el foco va al primer error o al resumen",
        "codes": [],
        "manual": True,
    },
    {
        "id": "error-summary",
        "section": "Comprensibilidad",
        "label": "Si el formulario es largo, existe un resumen de errores al inicio",
        "codes": [],
        "manual": True,
    },
    {
        "id": "preserve-data",
        "section": "Comprensibilidad",
        "label": "Los datos introducidos se conservan tras una validación fallida",
        "codes": [],
        "manual": True,
    },
    {
        "id": "legal-review",
        "section": "Comprensibilidad",
        "label": "Los procesos legales o económicos tienen revisión y confirmación antes del envío",
        "codes": [
            "WCAG2AA.Principle3.Guideline3_3.3_3_4",
        ],
        "manual": True,
    },
    {
        "id": "consistent-behavior",
        "section": "Comprensibilidad",
        "label": "Los componentes iguales se comportan de forma idéntica en todo el sitio",
        "codes": [
            "WCAG2AA.Principle3.Guideline3_2.3_2_4",
        ],
        "manual": True,
    },
    {
        "id": "no-unexpected-popup",
        "section": "Comprensibilidad",
        "label": "No aparecen ventanas emergentes inesperadas al enfocar o escribir en un campo",
        "codes": [
            "WCAG2AA.Principle3.Guideline3_2.3_2_1",
            "WCAG2AA.Principle3.Guideline3_2.3_2_2",
        ],
        "manual": True,
    },
    {
        "id": "cta-labels",
        "section": "Comprensibilidad",
        "label": "Las etiquetas de botones y llamadas a la acción son comprensibles y específicas",
        "codes": ["cta-labels"],
        "manual": False,
    },
    {
        "id": "success-messages",
        "section": "Comprensibilidad",
        "label": "Los mensajes de éxito confirman claramente el resultado de la acción",
        "codes": ["success-messages"],
        "manual": False,
    },
    {
        "id": "nav-consistency",
        "section": "Comprensibilidad",
        "label": "La navegación, menús y filtros son coherentes entre páginas",
        "codes": [
            "WCAG2AA.Principle3.Guideline3_2.3_2_3",
            "nav-consistency",
        ],
        "manual": False,
    },
    {
        "id": "filter-state",
        "section": "Comprensibilidad",
        "label": "Los filtros, ordenaciones y búsquedas muestran su estado actual",
        "codes": [],
        "manual": True,
    },
    {
        "id": "cookie-accessible",
        "section": "Comprensibilidad",
        "label": "Los avisos de cookies son operables por teclado y compatibles con lectores de pantalla",
        "codes": ["cookie-accessible"],
        "manual": False,
    },
    {
        "id": "legal-readable",
        "section": "Comprensibilidad",
        "label": "Los avisos legales y la política de privacidad son legibles y navegables",
        "codes": ["legal-readable"],
        "manual": False,
    },
    {
        "id": "new-tab-indication",
        "section": "Comprensibilidad",
        "label": "Los enlaces que abren nueva ventana o descargan un archivo lo indican",
        "codes": [
            "WCAG2AA.Principle3.Guideline3_2.3_2_5",
            "new-window-warning",
        ],
        "manual": False,
    },

    # ── ROBUSTEZ ─────────────────────────────────────────────────────────────
    {
        "id": "semantic-html",
        "section": "Robustez",
        "label": "Se utilizan elementos HTML semánticos (header, nav, main, footer, article…)",
        # Pa11y detecta ausencia de landmark principal <main>
        "codes": [
            "WCAG2AA.Principle1.Guideline1_3.1_3_1.H88",
            "WCAG2AA.Principle2.Guideline2_4.2_4_1",
            "Duplicate id",
            "semantic-landmarks",
        ],
        "manual": False,
    },
    {
        "id": "heading-hierarchy",
        "section": "Robustez",
        "label": "Los encabezados siguen una jerarquía lógica (H1 → H2 → H3…)",
        "codes": [
            "WCAG2AA.Principle1.Guideline1_3.1_3_1.G141",
            "heading-hierarchy",
        ],
        "manual": False,
    },
    {
        "id": "duplicate-id",
        "section": "Robustez",
        "label": "No existen atributos id duplicados en la misma página",
        "codes": [
            "WCAG2AA.Principle4.Guideline4_1.4_1_1.F77",
            "Duplicate id attribute value",
        ],
        "manual": False,
    },
    {
        "id": "valid-html",
        "section": "Robustez",
        "label": "El HTML es válido y los elementos están correctamente anidados",
        "codes": [
            "WCAG2AA.Principle4.Guideline4_1.4_1_1",
        ],
        "manual": False,
    },
]

SECTION_ORDER = ["Perceptibilidad", "Operabilidad", "Comprensibilidad", "Robustez"]


def map_issues_to_criteria(page_issues: list[dict]) -> list[dict]:
    """
    Given a list of pa11y issues for one page, return the criteria list
    annotated with matched issues and status.
    """
    result = []
    for criterion in CRITERIA:
        matched = []
        if criterion["codes"]:
            for idx, issue in enumerate(page_issues):
                code = issue.get("code", "")
                message = issue.get("message", "")
                for pattern in criterion["codes"]:
                    if pattern.lower() in code.lower() or pattern.lower() in message.lower():
                        issue_copy = dict(issue)
                        issue_copy["_idx"] = idx
                        matched.append(issue_copy)
                        break

        if criterion["manual"] and not matched:
            status = "manual"
        elif matched:
            status = "fail"
        else:
            status = "pass"

        result.append({
            "id": criterion["id"],
            "section": criterion["section"],
            "label": criterion["label"],
            "manual": criterion["manual"],
            "status": status,
            "issues": matched,
        })

    return result


def group_by_section(criteria_list: list[dict]) -> dict:
    """Group mapped criteria by section, preserving order."""
    sections = {s: [] for s in SECTION_ORDER}
    for c in criteria_list:
        sections[c["section"]].append(c)
    return sections
