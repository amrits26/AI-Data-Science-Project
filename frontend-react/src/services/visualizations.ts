import axios from "axios";

export async function fetchVisualizations(stockNumber: string) {
  // Returns all visualization data for a vehicle
  const { data } = await axios.get(`/api/visualizations/${stockNumber}`);
  return data;
}
