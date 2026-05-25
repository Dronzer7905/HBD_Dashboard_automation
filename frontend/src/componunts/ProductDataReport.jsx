import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  CardBody,
  Typography,
  Button,
  Spinner,
  Chip,
} from "@material-tailwind/react";
import {
  StarIcon,
  FireIcon,
  ShoppingBagIcon,
  ArrowTopRightOnSquareIcon,
  TagIcon,
  ArchiveBoxIcon,
  CurrencyRupeeIcon,
} from "@heroicons/react/24/solid";
import { TrophyIcon } from "@heroicons/react/24/outline";
import api from "../utils/Api";

const StarRating = ({ value }) => {
  if (!value) return <span className="text-gray-400 text-sm">—</span>;
  return (
    <span className="flex items-center gap-1 text-amber-500 font-semibold text-sm">
      <StarIcon className="h-4 w-4" />
      {Number(value).toFixed(1)}
    </span>
  );
};

export default function ProductDataReport() {
  const [products, setProducts] = useState([]);
  const [summary, setSummary]   = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetch = async () => {
      try {
        const [topRes, sumRes] = await Promise.all([
          api.get("/product-report/top-products"),
          api.get("/product-report/summary")
        ]);
        setProducts(topRes.data?.data || []);
        setSummary(sumRes.data?.data || null);
      } catch (e) {
        console.error(e);
        setError("Failed to load report data.");
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-4">
        <Spinner className="h-10 w-10 text-blue-500" />
        <Typography className="text-slate-500">Loading product report…</Typography>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-32">
        <Typography color="red" className="font-semibold">{error}</Typography>
      </div>
    );
  }

  return (
    <div className="mt-8 mb-12 px-4 xl:px-8">
      
      {/* --- Summary Section --- */}
      {summary && (
        <div className="mb-10">
          <Typography variant="h4" className="font-bold text-blue-gray-900 leading-tight mb-4">
            Dashboard Summary <span className="text-sm text-slate-500 font-normal ml-2">({summary.marketplace_name || 'Amazon'})</span>
          </Typography>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="border border-slate-100 shadow-sm">
              <CardBody className="p-4 flex items-center gap-4">
                <div className="p-3 bg-blue-50 rounded-lg">
                  <ShoppingBagIcon className="h-6 w-6 text-blue-500" />
                </div>
                <div>
                  <Typography variant="small" className="text-slate-500 font-medium">Total Products</Typography>
                  <Typography variant="h5" className="text-slate-800">{Number(summary.total_products).toLocaleString()}</Typography>
                </div>
              </CardBody>
            </Card>
            <Card className="border border-slate-100 shadow-sm">
              <CardBody className="p-4 flex items-center gap-4">
                <div className="p-3 bg-green-50 rounded-lg">
                  <TagIcon className="h-6 w-6 text-green-500" />
                </div>
                <div>
                  <Typography variant="small" className="text-slate-500 font-medium">Mapped Products</Typography>
                  <Typography variant="h5" className="text-slate-800">{Number(summary.mapped_products).toLocaleString()}</Typography>
                </div>
              </CardBody>
            </Card>
            <Card className="border border-slate-100 shadow-sm">
              <CardBody className="p-4 flex items-center gap-4">
                <div className="p-3 bg-orange-50 rounded-lg">
                  <ArchiveBoxIcon className="h-6 w-6 text-orange-500" />
                </div>
                <div>
                  <Typography variant="small" className="text-slate-500 font-medium">Total Categories</Typography>
                  <Typography variant="h5" className="text-slate-800">{Number(summary.total_categories).toLocaleString()}</Typography>
                </div>
              </CardBody>
            </Card>
            <Card className="border border-slate-100 shadow-sm">
              <CardBody className="p-4 flex items-center gap-4">
                <div className="p-3 bg-purple-50 rounded-lg">
                  <CurrencyRupeeIcon className="h-6 w-6 text-purple-500" />
                </div>
                <div>
                  <Typography variant="small" className="text-slate-500 font-medium">Avg Selling Price</Typography>
                  <Typography variant="h5" className="text-slate-800">₹{Number(summary.avg_selling_price).toLocaleString()}</Typography>
                </div>
              </CardBody>
            </Card>
          </div>
        </div>
      )}

      {/* --- Top Products Section --- */}
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-amber-50 rounded-xl">
          <TrophyIcon className="h-7 w-7 text-amber-500" />
        </div>
        <div>
          <Typography variant="h4" className="font-bold text-blue-gray-900 leading-tight">
            Top Selling Products
          </Typography>
          <Typography variant="small" className="text-slate-500">
            Top {products.length} products by ranking score
          </Typography>
        </div>
      </div>

      {/* Product grid */}
      {products.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-2">
          <ShoppingBagIcon className="h-12 w-12 text-slate-300" />
          <Typography className="text-slate-400 italic">No products found.</Typography>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {products.map((product, idx) => (
            <Card
              key={product.product_id || idx}
              className="border border-slate-100 shadow-sm hover:shadow-md transition-all duration-200 rounded-xl overflow-hidden flex flex-col"
            >
              {/* Product image */}
              <div className="relative bg-slate-50 flex items-center justify-center h-44 overflow-hidden">
                {product.img_url ? (
                  <img
                    src={product.img_url}
                    alt={product.product_name}
                    className="h-full w-full object-contain p-3"
                    onError={(e) => { e.target.style.display = "none"; }}
                  />
                ) : (
                  <ShoppingBagIcon className="h-16 w-16 text-slate-200" />
                )}

                {/* Rank badge */}
                <div className="absolute top-2 left-2 bg-blue-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                  #{idx + 1}
                </div>

                {/* Badges */}
                <div className="absolute top-2 right-2 flex flex-col gap-1">
                  {product.is_best_seller && (
                    <span className="flex items-center gap-1 bg-orange-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                      <FireIcon className="h-3 w-3" /> Best Seller
                    </span>
                  )}
                  {product.is_prime && (
                    <span className="bg-indigo-600 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                      Prime
                    </span>
                  )}
                </div>
              </div>

              <CardBody className="p-4 flex flex-col flex-1 gap-2">
                {/* Category */}
                <Typography variant="small" className="text-blue-600 font-semibold text-xs uppercase tracking-wide truncate">
                  {product.category_name || "—"}
                  {product.sub_category_name ? ` › ${product.sub_category_name}` : ""}
                </Typography>

                {/* Name */}
                <Typography
                  variant="paragraph"
                  className="font-bold text-slate-800 leading-snug line-clamp-2 text-sm"
                  title={product.product_name}
                >
                  {product.product_name || "—"}
                </Typography>

                {/* Brand */}
                {product.brand && (
                  <Typography variant="small" className="text-slate-500 text-xs">
                    by {product.brand}
                  </Typography>
                )}

                {/* Price row */}
                <div className="flex items-center gap-2 flex-wrap">
                  {product.price != null && (
                    <Typography className="font-bold text-slate-900 text-base">
                      ₹{Number(product.price).toLocaleString("en-IN")}
                    </Typography>
                  )}
                  {product.list_price && product.list_price > product.price && (
                    <Typography className="text-slate-400 text-xs line-through">
                      ₹{Number(product.list_price).toLocaleString("en-IN")}
                    </Typography>
                  )}
                  {product.discount && (
                    <Chip value={product.discount} color="green" size="sm" className="text-[10px] py-0.5 px-2" />
                  )}
                </div>

                {/* Stars + Reviews */}
                <div className="flex items-center gap-3">
                  <StarRating value={product.stars} />
                  {product.reviews > 0 && (
                    <Typography variant="small" className="text-slate-500 text-xs">
                      {Number(product.reviews).toLocaleString("en-IN")} reviews
                    </Typography>
                  )}
                </div>

                {/* Bought last month */}
                {product.bought_in_last_month > 0 && (
                  <Typography variant="small" className="text-emerald-600 text-xs font-medium">
                    {Number(product.bought_in_last_month).toLocaleString("en-IN")}+ bought last month
                  </Typography>
                )}

                {/* Ranking score */}
                <Typography variant="small" className="text-slate-400 text-xs">
                  Score: {Number(product.ranking_score || 0).toFixed(2)}
                </Typography>

                {/* Actions */}
                <div className="mt-auto pt-3 flex gap-2">
                  {product.asin ? (
                    <Button
                      size="sm"
                      color="blue"
                      className="flex-1 flex items-center justify-center gap-1 text-xs"
                      onClick={() => navigate(`/dashboard/productdata-report/products/${product.asin}`)}
                    >
                      View Details
                    </Button>
                  ) : (
                    <Button size="sm" color="gray" className="flex-1 text-xs" disabled>
                      No ASIN
                    </Button>
                  )}
                  {product.product_url && (
                    <Button
                      size="sm"
                      variant="outlined"
                      color="blue"
                      className="px-2"
                      onClick={() => window.open(product.product_url, "_blank")}
                    >
                      <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
