from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_project_card_does_not_use_article_as_button():
    source = _read(SRC / "components" / "ProjectCard.vue")
    workspace = _read(SRC / "views" / "NovelWorkspace.vue")

    assert '<article\n    class="md-card md-card-outlined project-card"' in source
    assert '@click="handleOpenProject"' not in source
    assert "cursor: pointer;" not in source
    assert '@click="enterProject(project)"' not in workspace


def test_llm_settings_feedback_is_announced_to_assistive_tech():
    source = _read(SRC / "components" / "LLMSettings.vue")

    assert ":role=\"saveFeedback.type === 'error' ? 'alert' : 'status'\"" in source
    assert 'aria-live="polite"' in source
    assert 'aria-atomic="true"' in source


def test_global_input_focus_does_not_animate_layout_properties():
    css = _read(SRC / "assets" / "main.css")

    assert "padding var(--md-duration-short)" not in css
    assert "padding: 15px" not in css
    assert ".md-text-field-input:focus-visible" in css
    assert ".md-textarea:focus-visible" in css


def test_motion_avoids_width_and_height_animation_for_auth_brand_and_ripple():
    main_css = _read(SRC / "assets" / "main.css")
    typewriter = _read(SRC / "components" / "TypewriterEffect.vue")

    assert "@keyframes typing" not in typewriter
    assert "animation: typing" not in typewriter
    assert "transition:\n    width 0.3s" not in main_css
    assert "height 0.3s" not in main_css


def test_shared_date_formatter_uses_intl_datetime_format():
    source = _read(SRC / "utils" / "date.ts")

    assert "Intl.DateTimeFormat" in source
    assert ".getFullYear()" not in source
    assert ".getMonth()" not in source
    assert ".getDate()" not in source


def test_index_declares_mobile_theme_color():
    source = _read(FRONTEND / "index.html")

    assert '<meta name="theme-color" content="#f4f0e9">' in source
