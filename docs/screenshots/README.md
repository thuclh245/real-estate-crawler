# Dashboard Screenshots

This directory stores dashboard screenshots used for project reports, demos, and progress evidence.

## Naming

Screenshots should use this format:

```text
{normalized_tab_name}_{YYYY-MM-DD}.png
```

Examples:

```text
overview_2026-05-14.png
pipeline_health_2026-05-14.png
listings_explorer_2026-05-14.png
```

Use `observability.generate_screenshot_filename()` to create stable filenames.

## Manual Capture

1. Start the dashboard:

   ```powershell
   streamlit run dashboard/app.py
   ```

2. Open the relevant tab.
3. Capture the browser window.
4. Save the PNG file into `docs/screenshots/` using the naming format above.

## Automated Capture

Automated screenshot scripts should call `ensure_screenshot_dir()` before saving files so this directory exists on fresh clones.
