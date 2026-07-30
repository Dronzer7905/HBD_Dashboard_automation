import React, { useState, useEffect } from "react";
import api from "../../utils/Api";

const DuplicateData = () => {
  const [data, setData] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalRecords, setTotalRecords] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState(""); // Search state

  const limit = 1000;
  const totalPages = Math.ceil(totalRecords / limit);

  useEffect(() => {
    fetchData(currentPage, search);
  }, [currentPage, search]);

  const fetchData = async (page, searchTerm = "") => {
    setLoading(true);
    setError(null);
    try {
      // Fix #1: correct endpoint (was /read_master_input/)
      // Fix #2: use Axios params object instead of manual query string
      const response = await api.get("/items/duplicates", {
        params: { page, limit, search: searchTerm },
      });
      // Fix #2: Axios auto-parses JSON — use response.data, not response.json()
      const result = response.data;
      setData(result.data || []);
      setTotalRecords(result.total_records || 0);
    } catch (err) {
      const status = err.response?.status;
      const message = err.response?.data?.message || err.response?.data?.error || err.message;
      if (status === 401) {
        setError("Session expired \u2014 please log in again.");
      } else if (status === 500) {
        setError(`Server error: ${message}`);
      } else {
        setError(`Error (${status || "network"}): ${message}`);
      }
      console.error("Error fetching duplicate data:", status, message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto my-8 px-4">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Duplicate Data</h2>
        <input
          type="text"
          className="border rounded-lg px-3 py-2 w-64 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Search by name, city, etc..."
          value={search}
          onChange={(e) => {
            setCurrentPage(1);
            setSearch(e.target.value);
          }}
        />
      </div>

      <div className="bg-white shadow rounded-lg p-4">
        {loading ? (
          <p className="text-center text-blue-500 font-semibold">Loading data...</p>
        ) : error ? (
          <p className="text-center text-red-600 font-semibold py-4">{error}</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full border border-gray-200 rounded-lg">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="px-2 py-2 text-left">ID</th>
                    <th className="px-2 py-2 text-left">Category</th>
                    <th className="px-2 py-2 text-left">City</th>
                    <th className="px-2 py-2 text-left">Name</th>
                    <th className="px-2 py-2 text-left">Area</th>
                    <th className="px-2 py-2 text-left">Address</th>
                    <th className="px-2 py-2 text-left">Phone No 1</th>
                    <th className="px-2 py-2 text-left">Phone No 2</th>
                    <th className="px-2 py-2 text-left">URL</th>
                    <th className="px-2 py-2 text-left">Ratings</th>
                    <th className="px-2 py-2 text-left">Sub Category</th>
                    <th className="px-2 py-2 text-left">State</th>
                    <th className="px-2 py-2 text-left">Country</th>
                    <th className="px-2 py-2 text-left">Email</th>
                    <th className="px-2 py-2 text-left">Latitude</th>
                    <th className="px-2 py-2 text-left">Longitude</th>
                    <th className="px-2 py-2 text-left">Reviews</th>
                    <th className="px-2 py-2 text-left">Facebook URL</th>
                    <th className="px-2 py-2 text-left">LinkedIn URL</th>
                    <th className="px-2 py-2 text-left">Twitter URL</th>
                    <th className="px-2 py-2 text-left">Description</th>
                    <th className="px-2 py-2 text-left">Pincode</th>
                    <th className="px-2 py-2 text-left">Virtual Phone No</th>
                    <th className="px-2 py-2 text-left">WhatsApp No</th>
                    <th className="px-2 py-2 text-left">Phone No 3</th>
                    <th className="px-2 py-2 text-left">Avg Spent</th>
                    <th className="px-2 py-2 text-left">Cost for Two</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((item, idx) => (
                    <tr key={idx} className="hover:bg-blue-50">
                      <td className="px-2 py-2">{item.id}</td>
                      <td className="px-2 py-2">{item.category}</td>
                      <td className="px-2 py-2">{item.city}</td>
                      <td className="px-2 py-2">{item.name}</td>
                      <td className="px-2 py-2">{item.area}</td>
                      <td className="px-2 py-2">{item.address}</td>
                      <td className="px-2 py-2">{item.phone_no_1}</td>
                      <td className="px-2 py-2">{item.phone_no_2}</td>
                      <td className="px-2 py-2">{item.url}</td>
                      <td className="px-2 py-2">{item.ratings}</td>
                      <td className="px-2 py-2">{item.sub_category}</td>
                      <td className="px-2 py-2">{item.state}</td>
                      <td className="px-2 py-2">{item.country}</td>
                      <td className="px-2 py-2">{item.email}</td>
                      <td className="px-2 py-2">{item.latitude}</td>
                      <td className="px-2 py-2">{item.longitude}</td>
                      <td className="px-2 py-2">{item.reviews}</td>
                      <td className="px-2 py-2">{item.facebook_url}</td>
                      <td className="px-2 py-2">{item.linkedin_url}</td>
                      <td className="px-2 py-2">{item.twitter_url}</td>
                      <td className="px-2 py-2">{item.description}</td>
                      <td className="px-2 py-2">{item.pincode}</td>
                      <td className="px-2 py-2">{item.virtual_phone}</td>
                      <td className="px-2 py-2">{item.whatsapp_no}</td>
                      <td className="px-2 py-2">{item.phone_no_3}</td>
                      <td className="px-2 py-2">{item.avg_spent}</td>
                      <td className="px-2 py-2">{item.cost_for_two}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex justify-center items-center mt-6 gap-2 flex-wrap">
              <button
                className="px-3 py-1 rounded bg-blue-500 text-white disabled:bg-gray-300"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((p) => p - 1)}
              >
                Previous
              </button>
              {Array.from({ length: totalPages }, (_, index) => (
                <button
                  key={index}
                  onClick={() => setCurrentPage(index + 1)}
                  className={`px-3 py-1 rounded border ${
                    currentPage === index + 1
                      ? "bg-blue-500 text-white"
                      : "bg-white text-blue-500"
                  }`}
                >
                  {index + 1}
                </button>
              ))}
              <button
                className="px-3 py-1 rounded bg-blue-500 text-white disabled:bg-gray-300"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default DuplicateData;
