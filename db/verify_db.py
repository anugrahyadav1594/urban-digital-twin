import pandas as pd
from db_config import get_engine

engine = get_engine()
tables = [
    'adivali_devad_roads', 'adivali_devad_buildings', 'adivali_devad_water', 'adivali_devad_bridges',
    'jnpt_port_roads', 'jnpt_port_buildings', 'jnpt_port_water', 'jnpt_port_bridges',
    'chandigarh_roads', 'chandigarh_buildings', 'chandigarh_water', 'chandigarh_bridges',
    'rotterdam_roads', 'rotterdam_buildings', 'rotterdam_water', 'rotterdam_bridges'
]

print(f"{'Table Name':<30} | {'Feature Count':<15}")
print("-" * 48)
for t in tables:
    try:
        cnt = pd.read_sql(f"SELECT count(*) FROM {t};", engine).iloc[0, 0]
        print(f"{t:<30} | {cnt:<15}")
    except Exception as e:
        print(f"{t:<30} | {'Table missing':<15}")
