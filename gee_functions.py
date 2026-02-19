# gee_functions.py
import ee

# Years we support
YEARS = [2020, 2021, 2022, 2023, 2024]

# Dynamic World palette (same as your JS)
CLASS_PALETTE = [
    "419bdf", "397d49", "88b053", "7a87c6", "e49635",
    "dfc35a", "c4281b", "a59b8f", "b39fe1"
]
CHANGE_COLOR = "ff00ff"  # magenta

# Default Abu Dhabi AOI: rectangle bounds (no EE calls yet)
DEFAULT_RECT_BOUNDS = [54.16, 24.29, 54.74, 24.61]


def get_aoi(bounds=None):
    """
    Return an EE geometry rectangle for the given bounds.
    bounds: [minLon, minLat, maxLon, maxLat] OR None to use default Abu Dhabi.
    """
    if bounds:
        # ensure we have floats
        try:
            b = [float(x) for x in bounds]
            if len(b) != 4:
                raise ValueError("bounds must be list-like of 4 floats")
            return ee.Geometry.Rectangle(b, None, False)
        except Exception as e:
            raise ValueError(f"Invalid bounds provided: {e}")
    # fallback to default
    return ee.Geometry.Rectangle(DEFAULT_RECT_BOUNDS, None, False)


def yearly_dw_label(year, roi=None):
    """Dynamic World label image for one year."""
    if roi is None:
        roi = get_aoi()

    start = ee.Date.fromYMD(int(year), 1, 1)
    end = start.advance(1, "year")
    img = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(roi)
        .filterDate(start, end)
        .select("label")
        .mode()
        .clip(roi)
        .unmask(0)
        .set("system:time_start", start.millis())
    )
    return img


def yearly_s2_rgb(year, roi=None):
    """Sentinel-2 RGB visual image for one year."""
    if roi is None:
        roi = get_aoi()

    start = ee.Date.fromYMD(int(year), 1, 1)
    end = start.advance(1, "year")
    s2 = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(roi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
    )
    median = s2.median().clip(roi)
    vis = median.visualize(bands=["B4", "B3", "B2"], min=0, max=3000)
    return vis


def make_change_image(year_a, year_b, roi=None):
    """Raw change mask (before visualize)."""
    if roi is None:
        roi = get_aoi()

    lbl_a = yearly_dw_label(year_a, roi)
    lbl_b = yearly_dw_label(year_b, roi)
    change = lbl_a.neq(lbl_b).selfMask().clip(roi)
    return change


def get_tile_template(image, vis_params, roi=None):
    """
    Get an interactive tile URL template for Leaflet, like:
    https://earthengine.googleapis.com/map/XYZ/{z}/{x}/{y}?token=ABC
    """
    # visualize first so colors are correct
    vis_image = image.visualize(**vis_params)
    m = vis_image.getMapId({})
    tile_url = m["tile_fetcher"].url_format
    return tile_url


def compare_dw_abudhabi_years(year_a: int, year_b: int, roi_bounds: list = None):
    """
    Main function.
    Accepts optional roi_bounds = [minLon, minLat, maxLon, maxLat]
    Returns:
      - PNG URLs (thumbs)
      - Tile URL templates (for interactive map)
    """

    year_a = int(year_a)
    year_b = int(year_b)

    # Ensure order and valid range
    if year_a > year_b:
        year_a, year_b = year_b, year_a

    if year_a not in YEARS or year_b not in YEARS:
        raise ValueError(f"Years must be between {YEARS[0]} and {YEARS[-1]}.")

    # Determine ROI
    if roi_bounds:
        roi = get_aoi(roi_bounds)
    else:
        roi = get_aoi()  # default Abu Dhabi

    # Build images
    dw_a_raw = yearly_dw_label(year_a, roi)
    dw_b_raw = yearly_dw_label(year_b, roi)
    s2_a_raw = yearly_s2_rgb(year_a, roi)
    s2_b_raw = yearly_s2_rgb(year_b, roi)
    change_raw = make_change_image(year_a, year_b, roi)

    # Visualization params
    dw_vis = {"min": 0, "max": 8, "palette": CLASS_PALETTE}
    # For S2 we already visualized in yearly_s2_rgb
    # Visual images for PNG thumbnails
    dw_a_vis = dw_a_raw.visualize(**dw_vis)
    dw_b_vis = dw_b_raw.visualize(**dw_vis)
    change_vis = change_raw.visualize(palette=[CHANGE_COLOR])

    # PNG thumbnail URLs (simple images)
    thumb_params = {
        "region": roi,
        "dimensions": 768,
        "format": "png",
    }

    dw_a_url = dw_a_vis.getThumbURL(thumb_params)
    dw_b_url = dw_b_vis.getThumbURL(thumb_params)
    s2_a_url = s2_a_raw.getThumbURL(thumb_params)
    s2_b_url = s2_b_raw.getThumbURL(thumb_params)
    change_url = change_vis.getThumbURL(thumb_params)

    # Tile URL templates (interactive map)
    dw_a_tiles = get_tile_template(dw_a_raw, dw_vis, roi)
    dw_b_tiles = get_tile_template(dw_b_raw, dw_vis, roi)
    change_tiles = get_tile_template(change_raw, {"palette": [CHANGE_COLOR]}, roi)

    result = {
        "year_a": year_a,
        "year_b": year_b,
        # PNGs
        "dw_a_url": dw_a_url,
        "dw_b_url": dw_b_url,
        "s2_a_url": s2_a_url,
        "s2_b_url": s2_b_url,
        "change_url": change_url,
        # Tiles
        "dw_a_tiles": dw_a_tiles,
        "dw_b_tiles": dw_b_tiles,
        "change_tiles": change_tiles,
    }
    return result
