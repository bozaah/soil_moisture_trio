import folium
import numpy as np
import xarray as xr

def create_interactive_map(
    classification_grid: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    data_grids: dict,
    output_path: str = "classification_map.html"
):
    """
    Generates an interactive HTML map with dry/wet classification overlay
    and popups displaying input data for each grid cell.

    Args:
        classification_grid (np.ndarray): 2D numpy array of classified dry/wet cells (0 for dry, 1 for wet).
        lats (np.ndarray): 1D numpy array of latitudes for the grid.
        lons (np.ndarray): 1D numpy array of longitudes for the grid.
        data_grids (dict): Dictionary containing the original data grids (soil_moisture, temperature, ndvi, vpd).
        output_path (str): Path to save the generated HTML map.
    """
    if not (lats.ndim == 1 and lons.ndim == 1):
        raise ValueError("lats and lons must be 1D arrays.")
    if not (classification_grid.shape == (len(lats), len(lons))):
        raise ValueError("classification_grid shape must match (len(lats), len(lons)).")

    # Calculate center of the map
    center_lat = np.mean(lats)
    center_lon = np.mean(lons)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=5)

    # Create a FeatureGroup for the classification overlay
    classification_layer = folium.FeatureGroup(name="Dry/Wet Classification").add_to(m)

    # Iterate through each grid cell to create rectangles and popups
    for i in range(len(lats) - 1):
        for j in range(len(lons) - 1):
            lat_min, lat_max = lats[i], lats[i+1]
            lon_min, lon_max = lons[j], lons[j+1]

            # Determine color based on classification
            color = "red" if classification_grid[i, j] == 0 else "blue"
            fill_color = color
            
            # Prepare popup content
            popup_html = f"""
            <b>Classification:</b> {'Wet' if classification_grid[i, j] == 1 else 'Dry'}<br>
            <b>Soil Moisture:</b> {data_grids['soil_moisture'][i, j]:.4f}<br>
            <b>Temperature (tmax):</b> {data_grids['temperature'][i, j]:.2f}<br>
            <b>NDVI (synthetic):</b> {data_grids['ndvi'][i, j]:.4f}<br>
            <b>VPD:</b> {data_grids['vpd'][i, j]:.2f}
            """

            # Add rectangle to the map
            folium.Rectangle(
                bounds=[(lat_min, lon_min), (lat_max, lon_max)],
                color=color,
                fill=True,
                fill_color=fill_color,
                fill_opacity=0.5,
                popup=folium.Popup(popup_html)
            ).add_to(classification_layer)

    folium.LayerControl().add_to(m)
    m.save(output_path)
    print(f"Interactive map saved to {output_path}")

if __name__ == '__main__':
    # Example usage (replace with actual pipeline output)
    # This part will be removed once integrated into main.py
    grid_size_lat = 10
    grid_size_lon = 10
    lats_example = np.linspace(-35, -25, grid_size_lat)
    lons_example = np.linspace(135, 145, grid_size_lon)
    
    # Synthetic classification grid
    classification_grid_example = np.random.randint(0, 2, size=(grid_size_lat -1, grid_size_lon -1))

    # Synthetic data grids
    data_grids_example = {
        'soil_moisture': np.random.uniform(0, 0.5, (grid_size_lat, grid_size_lon)),
        'temperature': np.random.uniform(15, 35, (grid_size_lat, grid_size_lon)),
        'ndvi': np.random.uniform(-0.1, 1.0, (grid_size_lat, grid_size_lon)),
        'vpd': np.random.uniform(0, 50, (grid_size_lat, grid_size_lon))
    }

    create_interactive_map(
        classification_grid_example,
        lats_example,
        lons_example,
        data_grids_example,
        "example_classification_map.html"
    )
