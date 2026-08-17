import json
from api.routes_map import get_master_map_by_region

for region in ['adivali_devad', 'jnpt_port', 'chandigarh', 'rotterdam']:
    response = get_master_map_by_region(region)
    data = json.loads(response.body.decode('utf-8'))
    print(f"{region.upper():<15} | Total Features: {data.get('feature_count')} | Layers: {data.get('layer_status')}")
