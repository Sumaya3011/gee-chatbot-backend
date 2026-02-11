import ee

# Years we support
YEARS = [2020, 2021, 2022, 2023, 2024]

# Same palette as your JS
CLASS_PALETTE = [
    "419bdf", "397d49", "88b053", "7a87c6", "e49635",
    "dfc35a", "c4281b", "a59b8f", "b39fe1"
]
CHANGE_COLOR = "ff00ff"  # magenta

# Abu Dhabi AOI: rectangle bounds (just numbers, no EE yet)
RECT_BOUNDS = [54.16, 24.29, 54.74, 24.61]


def get_aoi():
    """Return the Abu Dhabi AOI as an EE geometry."""
    return ee.Geometry.Rectangle(RECT_BOUNDS, None, False)


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


def make_change_layer(year_a, year_b, roi=None):
    """Magenta change layer where DW labels differ between two years."""
    if roi is None:
        roi = get_aoi()

    lbl_a = yearly_dw_label(year_a, roi)
    lbl_b = yearly_dw_label(year_b, roi)
    change = lbl_a.neq(lbl_b).selfMask().clip(roi)
    vis = change.visualize(palette=[CHANGE_COLOR])
    return vis


def compare_dw_abudhabi_years(year_a: int, year_b: int):
    """
    Main function.
    Returns URLs to PNG images for:
    - DW Year A
    - DW Year B
    - S2 Year A
    - S2 Year B
    - Change (A vs B)
    """

    year_a = int(year_a)
    year_b = int(year_b)

    if year_a > year_b:
        year_a, year_b = year_b, year_a

    if year_a not in YEARS or year_b not in YEARS:
        raise ValueError(f"Years must be between {YEARS[0]} and {YEARS[-1]}.")

    roi = get_aoi()

    dw_a = yearly_dw_label(year_a, roi).visualize(min=0, max=8, palette=CLASS_PALETTE)
    dw_b = yearly_dw_label(year_b, roi).visualize(min=0, max=8, palette=CLASS_PALETTE)
    s2_a = yearly_s2_rgb(year_a, roi)
    s2_b = yearly_s2_rgb(year_b, roi)
    change = make_change_layer(year_a, year_b, roi)

    thumb_params = {
        "region": roi,
        "dimensions": 768,
        "format": "png",
    }

    result = {
        "year_a": year_a,
            "year_b": year_b,
            "dw_a_url": dw_a.getThumbURL(thumb_params),
            "dw_b_url": dw_b.getThumbURL(thumb_params),
            "s2_a_url": s2_a.getThumbURL(thumb_params),
            "s2_b_url": s2_b.getThumbURL(thumb_params),
            "change_url": change.getThumbURL(thumb_params),
        }
    return result
