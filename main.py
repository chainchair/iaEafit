import osmnx as ox
import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
import json
import os

# Crear el archivo geojson

gdf = gpd.read_file("maps/eafit.geojson")

if not os.path.exists("maps/eafit.graphml"):
    # Usar el polígono para descargar la red de calles
    G = ox.graph_from_polygon(gdf.geometry[0], network_type="walk")
    # Guardar el grafo en un archivo GraphML para uso futuro
    ox.save_graphml(G, filepath="maps/eafit.graphml") 
    ox.save_graph_geopackage(G, filepath="maps/eafit.gpkg")

#cargar archivo si ya existia
G = ox.load_graphml("maps/eafit.graphml")
# Dibujar el grafo
#ox.plot_graph(G)

# edificios
if not os.path.exists("maps/eafit_buildings.geojson"):
    buildings = ox.features_from_polygon(gdf.geometry[0], tags={"building": True})
    buildings.to_file("maps/eafit_buildings.geojson", driver="GeoJSON")
else:
    buildings = gpd.read_file("maps/eafit_buildings.geojson")
    
# entradas y salidas
if not os.path.exists("maps/eafit_entrances.geojson"):
    entrances = ox.features_from_polygon(gdf.geometry[0], tags={"entrance": True})
    entrances.to_file("maps/eafit_entrances.geojson", driver="GeoJSON")
else:
    entrances = gpd.read_file("maps/eafit_entrances.geojson")

# asegurar mismo CRS
if entrances.crs != buildings.crs:
    entrances = entrances.to_crs(buildings.crs)
results = []
for idx, bloque in buildings.iterrows():
    entradas_bloque = entrances[entrances.intersects(bloque.geometry)]
    for _, e in entradas_bloque.iterrows():
        geom = e.geometry
        # si no es un punto (a veces OSM guarda como línea o polígono)
        if geom.geom_type != "Point":
            geom = geom.centroid
        results.append({
            "building": bloque.get("name", f"sin nombre {idx}"),
            "entrance": e.get("entrance", None),
            "geometry": geom
        })

df = gpd.GeoDataFrame(results, crs=entrances.crs)
df.to_file("maps/building_entrances.geojson", driver="GeoJSON")

entrances_with_nodes = []

# asegurar que CRS coincida con el grafo
if df.crs != G.graph["crs"]:
    df = df.to_crs(G.graph["crs"])

for idx, row in df.iterrows():
    geom = row.geometry
    if geom.is_empty:
        continue
    if geom.geom_type != "Point":
        geom = geom.centroid

    x, y = geom.x, geom.y
    try:
        nearest_node = ox.distance.nearest_nodes(G, x, y)
        entrances_with_nodes.append({
            "building": row["building"],
            "entrance": row["entrance"],
            "node": int(nearest_node)
        })
    except Exception as e:
        print(f"⚠️ Error en fila {idx} ({row['building']}): {e}")

# ========== 6. Guardar en JSON ==========
with open("maps/building_entrances_nodes.json", "w", encoding="utf-8") as f:
    json.dump(entrances_with_nodes, f, ensure_ascii=False, indent=2)

print("✅ Archivo 'building_entrances_nodes.json' creado con éxito")



# =====================================================================
# ========== 7. Ejemplo de consulta y ruta hacia un edificio ==========
# =====================================================================

# Cargar el JSON de entradas procesadas
with open("maps/building_entrances_nodes.json", encoding="utf-8") as f:
    entrances_data = json.load(f)

def get_building_nodes(building_name):
    nodes = [
        e["node"]
        for e in entrances_data
        if e.get("building") and e["building"].lower() == building_name.lower()
    ]
    return nodes

# Nodo de origen (ejemplo: primer nodo del grafo, ajusta según necesidad)
origin_node = list(G.nodes())[0]

# Definir edificio destino
target_building = "Bloque 7"
target_nodes = get_building_nodes(target_building)

if not target_nodes:
    print(f"⚠️ No se encontraron entradas para el edificio {target_building}")
else:
    best_route = None
    best_length = float("inf")

    for target in target_nodes:
        try:
            route = nx.shortest_path(G, origin_node, target, weight="length")
            length = nx.shortest_path_length(G, origin_node, target, weight="length")
            if length < best_length:
                best_length = length
                best_route = route
        except nx.NetworkXNoPath:
            continue

    if best_route:
        print(f"➡️ Ruta más corta hacia {target_building}:")
        print(best_route)
        print(f"Distancia: {best_length:.1f} metros")

        # Dibujar ruta
        fig, ax = ox.plot_graph_route(G, best_route, node_size=0, bgcolor="white")
        plt.show()
    else:
        print(f"❌ No se encontró ruta hacia {target_building}")