export const CITY_CENTER = {
  lon: Number(process.env.NEXT_PUBLIC_CITY_LON ?? 73.1405),
  lat: Number(process.env.NEXT_PUBLIC_CITY_LAT ?? 18.9972)
};

export const ION_TOKEN = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN ?? "";
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const NAVBAR_HEIGHT = 66;
export const TASKBAR_HEIGHT = 48;
