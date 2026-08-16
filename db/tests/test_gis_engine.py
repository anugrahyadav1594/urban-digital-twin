import unittest
import os
import geopandas as gpd
from shapely.geometry import Point, Polygon
from etl.coordinate_utils import get_pilot_sector_polygon, ensure_crs, STORAGE_CRS, PROJECTED_CRS
from etl.geometry_cleaner import clean_geometries
from api.routes_mcda import compute_site_suitability, SiteSuitabilityRequest, MCDAWeights
from api.routes_scenarios import compare_plans

class TestNagarXBackend(unittest.TestCase):

    def test_pilot_sector_polygon(self):
        sector_poly = get_pilot_sector_polygon()
        self.assertIsInstance(sector_poly, Polygon)
        minx, miny, maxx, maxy = sector_poly.bounds
        self.assertAlmostEqual(minx, 73.1300, places=4)
        self.assertAlmostEqual(miny, 18.9900, places=4)

    def test_crs_reprojection(self):
        gdf = gpd.GeoDataFrame([{'geometry': Point(73.14, 19.00)}], crs=STORAGE_CRS)
        gdf_proj = ensure_crs(gdf, PROJECTED_CRS)
        self.assertEqual(gdf_proj.crs.to_string(), PROJECTED_CRS)

    def test_geometry_cleaner(self):
        # Invalid self-intersecting bowtie polygon
        bowtie = Polygon([(0, 0), (0, 2), (2, 0), (2, 2), (0, 0)])
        gdf = gpd.GeoDataFrame([{'geometry': bowtie, 'list_col': [1, 2, 3]}], crs=STORAGE_CRS)
        cleaned = clean_geometries(gdf)
        self.assertTrue(cleaned.geometry.iloc[0].is_valid)
        self.assertNotIn('list_col', cleaned.columns)

    def test_mcda_site_suitability(self):
        req = SiteSuitabilityRequest(
            target_facility_type="hospital",
            weights=MCDAWeights(population_coverage=0.30, accessibility=0.20),
            top_k=3
        )
        res = compute_site_suitability(req)
        self.assertEqual(res["target_facility"], "hospital")
        self.assertEqual(len(res["top_candidates"]), 3)
        top_parcel = res["top_candidates"][0]
        self.assertIn("parcel_id", top_parcel)
        self.assertIn("score", top_parcel)
        self.assertGreaterEqual(top_parcel["score"], 50.0)

    def test_plan_comparison(self):
        res = compare_plans()
        self.assertIn("comparison", res)
        self.assertEqual(len(res["comparison"]), 3)
        self.assertIn("winning_recommendation", res)

if __name__ == "__main__":
    unittest.main()
