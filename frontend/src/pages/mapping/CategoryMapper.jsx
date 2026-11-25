import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../../configs/api";

const SOURCE_PAGE_SIZE = 50;
const CATEGORY_PAGE_SIZE = 200;
const PRODUCT_PAGE_SIZE = 50;
const REPORT_PAGE_SIZE = 25;
const MAX_PRODUCT_SELECTION = 100;

const PLATFORMS_LIST = [
  "Amazon",
  "BigBasket",
  "Blinkit",
  "DMart",
  "Flipkart",
  "IndiaMART",
  "JioMart",
  "Zepto",
  "Google Maps"
];

function getErrorMessage(error, fallback) {
  return (
    error?.response?.data?.message ||
    error?.response?.data?.error ||
    error?.message ||
    fallback
  );
}

function getPayload(response) {
  const payload = response?.data?.data;
  if (!payload || typeof payload !== "object") {
    throw new Error("The category mapping API returned an invalid response.");
  }
  return payload;
}

function getProductPath(category) {
  return (
    category.category_path ||
    [
      category.category_name,
      category.subcategory_name,
      category.child_category_name,
    ]
      .filter(Boolean)
      .join(" > ")
  );
}

function getPlatformBadge(name) {
  const key = (name || "").toLowerCase();
  if (key.includes("amazon")) {
    return "bg-amber-100 text-amber-800 border-amber-300";
  }
  if (key.includes("flipkart")) {
    return "bg-sky-100 text-sky-800 border-sky-300";
  }
  if (key.includes("blinkit")) {
    return "bg-yellow-100 text-yellow-800 border-yellow-300";
  }
  if (key.includes("zepto")) {
    return "bg-purple-100 text-purple-800 border-purple-300";
  }
  if (key.includes("dmart")) {
    return "bg-blue-100 text-blue-800 border-blue-300";
  }
  if (key.includes("bigbasket")) {
    return "bg-emerald-100 text-emerald-800 border-emerald-300";
  }
  if (key.includes("indiamart")) {
    return "bg-teal-100 text-teal-800 border-teal-300";
  }
  if (key.includes("jiomart")) {
    return "bg-rose-100 text-rose-800 border-rose-300";
  }
  return "bg-gray-100 text-gray-800 border-gray-300";
}

function StatusMessage({ message, onDismiss }) {
  if (!message) return null;

  const colors =
    message.type === "error"
      ? "border-red-200 bg-red-50 text-red-800"
      : message.type === "success"
        ? "border-green-200 bg-green-50 text-green-800"
        : "border-blue-200 bg-blue-50 text-blue-800";

  return (
    <div
      role={message.type === "error" ? "alert" : "status"}
      aria-live="polite"
      className={`mb-5 flex items-start justify-between gap-4 rounded-lg border px-4 py-3 text-sm ${colors}`}
    >
      <p>{message.text}</p>
      <button
        type="button"
        onClick={onDismiss}
        className="shrink-0 font-semibold underline"
        aria-label="Dismiss message"
      >
        Dismiss
      </button>
    </div>
  );
}

function CategoryMapper() {
  const [activeTab, setActiveTab] = useState("report"); // "report" | "mapper" | "analytics"

  // ═════════════════════════════════════════════════════════════════════
  // TAB 1: BUSINESS-TO-PRODUCT MAPPINGS & EXECUTIVE REPORT
  // ═════════════════════════════════════════════════════════════════════
  const [bpStats, setBpStats] = useState(null);
  const [bpMappings, setBpMappings] = useState([]);
  const [bpPage, setBpPage] = useState(1);
  const [bpTotalPages, setBpTotalPages] = useState(1);
  const [bpTotalCount, setBpTotalCount] = useState(0);
  const [bpLoading, setBpLoading] = useState(false);
  const [bpSearch, setBpSearch] = useState("");
  const [bpSearchInput, setBpSearchInput] = useState("");
  const [bpBusinessFilter, setBpBusinessFilter] = useState("");
  const [bpMarketplaceFilter, setBpMarketplaceFilter] = useState("");

  // Automated Matcher state
  const [autoDiscoverLoading, setAutoDiscoverLoading] = useState(false);
  const [autoSuggestions, setAutoSuggestions] = useState([]);
  const [bulkApproving, setBulkApproving] = useState(false);

  // ═════════════════════════════════════════════════════════════════════
  // TAB 2: INTERACTIVE 3-PANE CATEGORY MAPPER
  // ═════════════════════════════════════════════════════════════════════
  const [sourceRows, setSourceRows] = useState([]);
  const [sourcePage, setSourcePage] = useState(1);
  const [sourceTotalPages, setSourceTotalPages] = useState(1);
  const [sourceTotalCount, setSourceTotalCount] = useState(0);
  const [sourceSearchInput, setSourceSearchInput] = useState("");
  const [sourceSearch, setSourceSearch] = useState("");
  const [sourceStatusFilter, setSourceStatusFilter] = useState("all");
  const [sourcePlatformFilter, setSourcePlatformFilter] = useState("");
  const [sourceLoading, setSourceLoading] = useState(true);
  const [sourceError, setSourceError] = useState("");
  const [selectedSource, setSelectedSource] = useState(null);

  const [businessCategories, setBusinessCategories] = useState([]);
  const [businessCategoriesLoading, setBusinessCategoriesLoading] = useState(true);
  const [businessCategoriesError, setBusinessCategoriesError] = useState("");
  const [selectedBusinessId, setSelectedBusinessId] = useState("");
  const [selectedSubcategoryId, setSelectedSubcategoryId] = useState("");

  const [productCategories, setProductCategories] = useState([]);
  const [productLookup, setProductLookup] = useState({});
  const [productPage, setProductPage] = useState(1);
  const [productTotalPages, setProductTotalPages] = useState(1);
  const [productSearchInput, setProductSearchInput] = useState("");
  const [productSearch, setProductSearch] = useState("");
  const [productMarketplaceFilter, setProductMarketplaceFilter] = useState("");
  const [productLoading, setProductLoading] = useState(true);
  const [productError, setProductError] = useState("");
  const [selectedProductIds, setSelectedProductIds] = useState([]);

  const [capabilities, setCapabilities] = useState(null);
  const [autoMapLoading, setAutoMapLoading] = useState(false);
  const [autoMapResults, setAutoMapResults] = useState({});
  const [autoMapSummary, setAutoMapSummary] = useState(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  // ───────────────────────────────────────────────────────────────────
  // LOAD BUSINESS-TO-PRODUCT STATS & MAPPINGS
  // ───────────────────────────────────────────────────────────────────
  const loadBpStats = useCallback(async () => {
    try {
      const res = await api.get("/mapping/business-products/stats");
      if (res.data?.status === "success") {
        setBpStats(res.data.data);
      }
    } catch (err) {
      console.error("Failed to load business-product mapping stats", err);
    }
  }, []);

  const loadBpMappings = useCallback(async (page, search, bId, market) => {
    setBpLoading(true);
    try {
      const params = {
        page,
        limit: REPORT_PAGE_SIZE,
        search: search || undefined,
        business_category_id: bId || undefined,
        marketplace_name: market || undefined,
      };
      const res = await api.get("/mapping/business-products", { params });
      if (res.data?.status === "success") {
        const payload = res.data.data;
        setBpMappings(payload.data || []);
        setBpPage(payload.current_page || 1);
        setBpTotalPages(payload.total_pages || 1);
        setBpTotalCount(payload.total_count || 0);
      }
    } catch (err) {
      setMessage({
        type: "error",
        text: getErrorMessage(err, "Failed to load business-to-product mapping report."),
      });
    } finally {
      setBpLoading(false);
    }
  }, []);

  // ───────────────────────────────────────────────────────────────────
  // AUTO-DISCOVER & BULK APPROVE FOR BUSINESS PRODUCTS
  // ───────────────────────────────────────────────────────────────────
  const runAutoDiscover = async () => {
    setAutoDiscoverLoading(true);
    setAutoSuggestions([]);
    setMessage(null);
    try {
      const res = await api.post("/mapping/business-products/auto-map", {
        business_category_id: bpBusinessFilter || undefined,
        marketplace_name: bpMarketplaceFilter || undefined,
        limit: 100,
        threshold: 0.80,
      });
      if (res.data?.status === "success") {
        const data = res.data.data || [];
        setAutoSuggestions(data);
        if (data.length === 0) {
          setMessage({
            type: "info",
            text: "No new automated match suggestions found above 80% confidence.",
          });
        } else {
          setMessage({
            type: "success",
            text: `Discovered ${data.length} high-confidence product match suggestions (80%+) for review.`,
          });
        }
      }
    } catch (err) {
      setMessage({
        type: "error",
        text: getErrorMessage(err, "Failed to run automated category discovery."),
      });
    } finally {
      setAutoDiscoverLoading(false);
    }
  };

  const handleBulkApprove = async () => {
    if (autoSuggestions.length === 0) return;
    setBulkApproving(true);
    setMessage(null);
    try {
      const res = await api.post("/mapping/business-products/approve", {
        items: autoSuggestions,
      });
      if (res.data?.status === "success") {
        const saved = res.data.data?.saved || 0;
        setMessage({
          type: "success",
          text: `Bulk approved ${saved} business-to-product mapping associations successfully!`,
        });
        setAutoSuggestions([]);
        loadBpStats();
        loadBpMappings(1, bpSearch, bpBusinessFilter, bpMarketplaceFilter);
      }
    } catch (err) {
      setMessage({
        type: "error",
        text: getErrorMessage(err, "Failed to bulk approve mappings."),
      });
    } finally {
      setBulkApproving(false);
    }
  };

  const handleApproveSingleSuggestion = async (item) => {
    try {
      const res = await api.post("/mapping/business-products/approve", {
        items: [item],
      });
      if (res.data?.status === "success") {
        setMessage({
          type: "success",
          text: `Approved association between ${item.business_subcategory_name} and ${item.marketplace_name} (${item.category_path}).`,
        });
        setAutoSuggestions((prev) =>
          prev.filter(
            (s) =>
              !(
                s.business_subcategory_id === item.business_subcategory_id &&
                s.product_category_id === item.product_category_id
              ),
          ),
        );
        loadBpStats();
        loadBpMappings(bpPage, bpSearch, bpBusinessFilter, bpMarketplaceFilter);
      }
    } catch (err) {
      setMessage({
        type: "error",
        text: getErrorMessage(err, "Failed to approve mapping."),
      });
    }
  };

  const handleDeleteMapping = async (mappingId) => {
    if (!window.confirm("Are you sure you want to delete this mapping association?")) return;
    try {
      const res = await api.delete(`/mapping/business-products/${mappingId}`);
      if (res.data?.status === "success") {
        setMessage({
          type: "success",
          text: "Mapping association removed successfully.",
        });
        loadBpStats();
        loadBpMappings(bpPage, bpSearch, bpBusinessFilter, bpMarketplaceFilter);
      }
    } catch (err) {
      setMessage({
        type: "error",
        text: getErrorMessage(err, "Failed to delete mapping association."),
      });
    }
  };

  // ───────────────────────────────────────────────────────────────────
  // TAB 2: INTERACTIVE MAPPER LOADERS
  // ───────────────────────────────────────────────────────────────────
  const loadSources = useCallback(async (page, search, status, platform) => {
    setSourceLoading(true);
    setSourceError("");
    try {
      const params = {
        status: status || "all",
        platform_name: platform || undefined,
        page,
        limit: SOURCE_PAGE_SIZE,
        search: search || undefined,
        category_limit: 1,
        product_limit: 1,
      };
      const payload = getPayload(
        await api.get("/mapping/categories", { params }),
      );
      const result = payload.source_categories;
      if (!result || !Array.isArray(result.data)) {
        throw new Error("The source category list is missing from the API response.");
      }

      setSourceRows(result.data);
      setSourcePage(result.current_page || page);
      setSourceTotalPages(result.total_pages || 1);
      setSourceTotalCount(result.total_count || 0);
      setCapabilities(payload.capabilities || null);
      setSelectedSource((current) =>
        current && result.data.some((row) => row.id === current.id)
          ? current
          : null,
      );
    } catch (error) {
      setSourceError(getErrorMessage(error, "Unable to load source categories."));
    } finally {
      setSourceLoading(false);
    }
  }, []);

  const loadBusinessCategories = useCallback(async () => {
    setBusinessCategoriesLoading(true);
    setBusinessCategoriesError("");
    try {
      const firstPayload = getPayload(
        await api.get("/mapping/categories", {
          params: {
            status: "all",
            limit: 1,
            category_page: 1,
            category_limit: CATEGORY_PAGE_SIZE,
            product_limit: 1,
          },
        }),
      );
      const firstPage = firstPayload.canonical_categories;
      if (!firstPage || !Array.isArray(firstPage.data)) {
        throw new Error("The master business category list is missing from the API response.");
      }

      const pages = [firstPage.data];
      const totalPages = Math.min(firstPage.total_pages || 1, 5); // Load up to 1000 categories for smooth browsing
      for (let page = 2; page <= totalPages; page += 1) {
        const payload = getPayload(
          await api.get("/mapping/categories", {
            params: {
              status: "all",
              limit: 1,
              category_page: page,
              category_limit: CATEGORY_PAGE_SIZE,
              product_limit: 1,
            },
          }),
        );
        if (Array.isArray(payload.canonical_categories?.data)) {
          pages.push(payload.canonical_categories.data);
        }
      }

      setBusinessCategories(pages.flat());
      setCapabilities(firstPayload.capabilities || null);
    } catch (error) {
      setBusinessCategoriesError(
        getErrorMessage(error, "Unable to load master business categories."),
      );
    } finally {
      setBusinessCategoriesLoading(false);
    }
  }, []);

  const loadProducts = useCallback(async (page, search, marketplace) => {
    setProductLoading(true);
    setProductError("");
    try {
      const params = {
        status: "all",
        limit: 1,
        category_limit: 1,
        product_page: page,
        product_limit: PRODUCT_PAGE_SIZE,
        product_search: search || undefined,
        marketplace_name: marketplace || undefined,
      };
      const payload = getPayload(
        await api.get("/mapping/categories", { params }),
      );
      const result = payload.product_service_categories;
      if (!result || !Array.isArray(result.data)) {
        throw new Error("The product category list is missing from the API response.");
      }

      setProductCategories(result.data);
      setProductPage(result.current_page || page);
      setProductTotalPages(result.total_pages || 1);
      setProductLookup((current) => {
        const next = { ...current };
        result.data.forEach((category) => {
          next[category.id] = category;
        });
        return next;
      });
      setCapabilities(payload.capabilities || null);
    } catch (error) {
      setProductError(getErrorMessage(error, "Unable to load product categories."));
    } finally {
      setProductLoading(false);
    }
  }, []);

  // ───────────────────────────────────────────────────────────────────
  // INITIAL LIFECYCLE
  // ───────────────────────────────────────────────────────────────────
  useEffect(() => {
    loadBpStats();
    loadBpMappings(1, "", "", "");
    loadSources(1, "", "all", "");
    loadBusinessCategories();
    loadProducts(1, "", "");
  }, [loadBpStats, loadBpMappings, loadSources, loadBusinessCategories, loadProducts]);

  const businessOptions = useMemo(
    () =>
      businessCategories.filter(
        (category) => category.level === 1 && category.parent_id == null,
      ),
    [businessCategories],
  );

  const subcategoryOptions = useMemo(
    () =>
      businessCategories.filter(
        (category) =>
          category.level === 2 &&
          Number(category.parent_id) === Number(selectedBusinessId),
      ),
    [businessCategories, selectedBusinessId],
  );

  const selectedProducts = useMemo(
    () =>
      selectedProductIds
        .map((id) => productLookup[id])
        .filter(Boolean),
    [productLookup, selectedProductIds],
  );

  // ───────────────────────────────────────────────────────────────────
  // SEARCH & FILTER HANDLERS
  // ───────────────────────────────────────────────────────────────────
  const handleReportSearch = (e) => {
    e.preventDefault();
    const q = bpSearchInput.trim();
    setBpSearch(q);
    loadBpMappings(1, q, bpBusinessFilter, bpMarketplaceFilter);
  };

  const handleBusinessFilterChange = (bId) => {
    setBpBusinessFilter(bId);
    loadBpMappings(1, bpSearch, bId, bpMarketplaceFilter);
  };

  const handleMarketplaceFilterChange = (mkt) => {
    setBpMarketplaceFilter(mkt);
    loadBpMappings(1, bpSearch, bpBusinessFilter, mkt);
  };

  const handleSourceSearch = (event) => {
    event.preventDefault();
    const search = sourceSearchInput.trim();
    setSourceSearch(search);
    setSourcePage(1);
    loadSources(1, search, sourceStatusFilter, sourcePlatformFilter);
  };

  const handleSourceStatusChange = (status) => {
    setSourceStatusFilter(status);
    setSourcePage(1);
    loadSources(1, sourceSearch, status, sourcePlatformFilter);
  };

  const handleSourcePlatformChange = (platform) => {
    setSourcePlatformFilter(platform);
    setSourcePage(1);
    loadSources(1, sourceSearch, sourceStatusFilter, platform);
  };

  const handleProductSearch = (event) => {
    event.preventDefault();
    const search = productSearchInput.trim();
    setProductSearch(search);
    loadProducts(1, search, productMarketplaceFilter);
  };

  const handleProductMarketplaceChange = (mkt) => {
    setProductMarketplaceFilter(mkt);
    loadProducts(1, productSearch, mkt);
  };

  const toggleProduct = (category) => {
    setProductLookup((current) => ({ ...current, [category.id]: category }));
    setSelectedProductIds((current) => {
      if (current.includes(category.id)) {
        return current.filter((id) => id !== category.id);
      }
      if (current.length >= MAX_PRODUCT_SELECTION) {
        setMessage({
          type: "error",
          text: `Select no more than ${MAX_PRODUCT_SELECTION} product categories.`,
        });
        return current;
      }
      return [...current, category.id];
    });
  };

  const chooseSuggestion = (suggestion) => {
    const candidate = suggestion?.candidates?.[0];
    if (!candidate || suggestion.classification === "ambiguous") return;

    let node = businessCategories.find(
      (category) => Number(category.id) === Number(candidate.id),
    );
    while (node && node.level > 2) {
      node = businessCategories.find(
        (category) => Number(category.id) === Number(node.parent_id),
      );
    }

    if (node?.level === 2) {
      setSelectedBusinessId(String(node.parent_id));
      setSelectedSubcategoryId(String(node.id));
    } else if (node?.level === 1) {
      setSelectedBusinessId(String(node.id));
      setSelectedSubcategoryId("");
    }
    setMessage({
      type: "info",
      text: "Suggestion selected for review. Click 'Approve mapping' below to persist.",
    });
  };

  const runAutoMap = async () => {
    setAutoMapLoading(true);
    setAutoMapSummary(null);
    setMessage(null);
    try {
      const response = await api.post("/mapping/auto-map", {
        dry_run: true,
        limit: 50,
      });
      const payload = response.data;
      if (!payload || payload.status !== "success" || !Array.isArray(payload.data)) {
        throw new Error(payload?.message || "The auto-map API returned an invalid response.");
      }

      const results = {};
      payload.data.forEach((result) => {
        results[result.mapping_id] = result;
      });
      setAutoMapResults(results);
      setAutoMapSummary(payload);
      const suggestions = payload.data.filter(
        (result) =>
          result.candidates?.[0]?.score >= 0.8 &&
          result.classification !== "ambiguous",
      ).length;
      setMessage({
        type: "success",
        text: `Preview complete: ${suggestions} unambiguous suggestion(s) scored at least 80%. No mappings were saved.`,
      });
    } catch (error) {
      setMessage({
        type: "error",
        text: getErrorMessage(error, "Unable to generate auto-map suggestions."),
      });
    } finally {
      setAutoMapLoading(false);
    }
  };

  const approveMapping = async () => {
    if (!selectedSource || !selectedBusinessId || !selectedSubcategoryId) {
      setMessage({
        type: "error",
        text: "Select an unmapped source, a business category, and a subcategory.",
      });
      return;
    }
    if (selectedProductIds.length === 0) {
      setMessage({
        type: "error",
        text: "Select at least one product category to create the association.",
      });
      return;
    }
    if (!capabilities?.business_product_associations) {
      setMessage({
        type: "error",
        text:
          capabilities?.limitation ||
          "Business-to-product associations are disabled by the backend configuration.",
      });
      return;
    }

    setSaving(true);
    setMessage(null);
    let associationsSaved = false;
    try {
      const associationResponse = await api.post("/mapping/map-category", {
        business_category_id: Number(selectedBusinessId),
        business_subcategory_id: Number(selectedSubcategoryId),
        product_category_ids: selectedProductIds,
        mapping_type: "carries_products",
      });
      associationsSaved = true;

      await api.post("/mapping/map-category", {
        mapping_id: selectedSource.id,
        master_category_id: Number(selectedSubcategoryId),
        parent_category_id: Number(selectedBusinessId),
      });

      const associationCount =
        associationResponse.data?.data?.saved ?? selectedProductIds.length;
      setMessage({
        type: "success",
        text: `Mapping approved! ${associationCount} product association(s) saved to database.`,
      });
      setSelectedSource(null);
      setSelectedBusinessId("");
      setSelectedSubcategoryId("");
      setSelectedProductIds([]);
      setAutoMapResults((current) => {
        const next = { ...current };
        delete next[selectedSource.id];
        return next;
      });
      loadSources(sourcePage, sourceSearch, sourceStatusFilter, sourcePlatformFilter);
      loadBpStats();
      loadBpMappings(1, bpSearch, bpBusinessFilter, bpMarketplaceFilter);
    } catch (error) {
      const details = getErrorMessage(error, "The mapping request failed.");
      setMessage({
        type: "error",
        text: associationsSaved
          ? `Product associations were saved, but source category update encountered an error: ${details}.`
          : details,
      });
    } finally {
      setSaving(false);
    }
  };

  const capabilitiesReady = capabilities !== null;
  const associationsEnabled = capabilities?.business_product_associations === true;
  const canApprove =
    Boolean(selectedSource) &&
    Boolean(selectedBusinessId) &&
    Boolean(selectedSubcategoryId) &&
    selectedProductIds.length > 0 &&
    associationsEnabled &&
    !saving;

  return (
    <main className="min-h-screen bg-blue-gray-50/50 p-4 md:p-6">
      {/* ─────────────────────────────────────────────────────────────
          PAGE HEADER
      ───────────────────────────────────────────────────────────── */}
      <header className="mb-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-blue-600">
              CityHangaround Automation Master &bull; Catalog Center
            </p>
            <h1 className="mt-1 text-2xl md:text-3xl font-extrabold text-blue-gray-900 tracking-tight">
              Business Categories &amp; Product Mapping Dashboard
            </h1>
            <p className="mt-1 max-w-4xl text-sm text-blue-gray-600">
              Automated end-to-end mapping linking Business Listing Categories &amp; Subcategories with Multi-Platform E-commerce Catalogs (Amazon, Flipkart, Blinkit, Zepto, DMart, BigBasket, IndiaMART, JioMart).
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                loadBpStats();
                loadBpMappings(bpPage, bpSearch, bpBusinessFilter, bpMarketplaceFilter);
                loadSources(sourcePage, sourceSearch, sourceStatusFilter, sourcePlatformFilter);
                loadProducts(productPage, productSearch, productMarketplaceFilter);
              }}
              className="rounded-lg border border-blue-gray-200 bg-white px-3.5 py-2 text-xs font-bold text-blue-gray-700 shadow-sm hover:bg-blue-gray-50 transition"
            >
              ↻ Refresh Data
            </button>
            <span className="rounded-full bg-blue-600 px-3.5 py-1 text-xs font-bold text-white shadow-sm">
              All 8 Platforms Active
            </span>
          </div>
        </div>

        {/* ─────────────────────────────────────────────────────────────
            EXECUTIVE KPI STAT CARDS
        ───────────────────────────────────────────────────────────── */}
        {bpStats && (
          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-4">
            <div className="rounded-xl border border-blue-100 bg-white p-4 shadow-sm">
              <span className="text-[11px] font-bold uppercase text-blue-600">
                Business Taxonomy
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-black text-blue-gray-900">
                  {bpStats.total_business_categories}
                </span>
                <span className="text-xs text-blue-gray-500 font-medium">
                  Categories ({bpStats.total_business_subcategories} Subcategories)
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-emerald-100 bg-white p-4 shadow-sm">
              <span className="text-[11px] font-bold uppercase text-emerald-700">
                Mapped Relationships
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-black text-emerald-600">
                  {bpStats.total_associations}
                </span>
                <span className="text-xs text-emerald-700 font-semibold">
                  Approved in DB
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-indigo-100 bg-white p-4 shadow-sm">
              <span className="text-[11px] font-bold uppercase text-indigo-700">
                Subcategory Coverage
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-black text-indigo-900">
                  {bpStats.subcategory_coverage_percent}%
                </span>
                <span className="text-xs text-indigo-600 font-medium">
                  ({bpStats.mapped_subcategories_count} of {bpStats.total_business_subcategories})
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-purple-100 bg-white p-4 shadow-sm">
              <span className="text-[11px] font-bold uppercase text-purple-700">
                Product Catalog Size
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-black text-purple-900">
                  {bpStats.total_product_categories.toLocaleString()}
                </span>
                <span className="text-xs text-purple-700 font-medium">
                  Across 8 Platforms
                </span>
              </div>
            </div>
          </div>
        )}

        {/* ─────────────────────────────────────────────────────────────
            TAB NAVIGATION BAR
        ───────────────────────────────────────────────────────────── */}
        <div className="mt-6 flex border-b border-blue-gray-200">
          <button
            onClick={() => setActiveTab("report")}
            className={`flex items-center gap-2 border-b-2 px-5 py-3 text-sm font-bold transition ${
              activeTab === "report"
                ? "border-blue-600 text-blue-600 bg-white rounded-t-lg shadow-sm"
                : "border-transparent text-blue-gray-600 hover:text-blue-900 hover:border-blue-gray-300"
            }`}
          >
            <span>&bull;</span> Executive Mapping Report &amp; Approval Center
            <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-800">
              {bpTotalCount}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("mapper")}
            className={`flex items-center gap-2 border-b-2 px-5 py-3 text-sm font-bold transition ${
              activeTab === "mapper"
                ? "border-blue-600 text-blue-600 bg-white rounded-t-lg shadow-sm"
                : "border-transparent text-blue-gray-600 hover:text-blue-900 hover:border-blue-gray-300"
            }`}
          >
            <span>&bull;</span> Interactive Category Mapper (3-Pane)
          </button>

          <button
            onClick={() => setActiveTab("analytics")}
            className={`flex items-center gap-2 border-b-2 px-5 py-3 text-sm font-bold transition ${
              activeTab === "analytics"
                ? "border-blue-600 text-blue-600 bg-white rounded-t-lg shadow-sm"
                : "border-transparent text-blue-gray-600 hover:text-blue-900 hover:border-blue-gray-300"
            }`}
          >
            <span>&bull;</span> Platform Coverage Breakdown
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800">
              8 Marketplaces
            </span>
          </button>
        </div>
      </header>

      <StatusMessage message={message} onDismiss={() => setMessage(null)} />

      {/* ═════════════════════════════════════════════════════════════════
          TAB 1: BUSINESS-TO-PRODUCT MAPPINGS & ONE-CLICK APPROVAL
      ═════════════════════════════════════════════════════════════════ */}
      {activeTab === "report" && (
        <div className="space-y-6">
          {/* Automated Discovery & Bulk Approval Callout */}
          <section className="rounded-2xl border border-blue-200 bg-gradient-to-r from-blue-50 via-indigo-50 to-white p-5 shadow-sm">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="max-w-3xl">
                <div className="flex items-center gap-2">
                  <span className="rounded-md bg-blue-600 px-2.5 py-0.5 text-[11px] font-extrabold text-white uppercase tracking-wider">
                    Automated Discovery Engine
                  </span>
                  <span className="text-xs font-bold text-blue-800">
                    Confidence-Scored Matcher
                  </span>
                </div>
                <h3 className="mt-1.5 text-lg font-bold text-blue-gray-900">
                  Automate Business-to-Product Mapping with 1-Click Approval
                </h3>
                <p className="mt-1 text-xs text-blue-gray-600">
                  The automated engine evaluates semantic overlap between local business directory subcategories and product categories across Amazon, Flipkart, Blinkit, Zepto, DMart, BigBasket, IndiaMART, and JioMart. Review confidence scores and approve in bulk or individually.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2.5 shrink-0">
                <button
                  type="button"
                  onClick={runAutoDiscover}
                  disabled={autoDiscoverLoading}
                  className="rounded-lg border border-blue-300 bg-white px-4 py-2 text-xs font-bold text-blue-700 shadow-sm hover:bg-blue-50 disabled:opacity-50 transition"
                >
                  {autoDiscoverLoading ? "Scanning Catalogs..." : "↻ Auto-Discover Matches (Preview)"}
                </button>

                {autoSuggestions.length > 0 && (
                  <button
                    type="button"
                    onClick={handleBulkApprove}
                    disabled={bulkApproving}
                    className="rounded-lg bg-green-600 px-4 py-2 text-xs font-bold text-white shadow hover:bg-green-700 disabled:opacity-50 transition"
                  >
                    {bulkApproving
                      ? "Persisting Approvals..."
                      : `✓ Bulk Approve All ${autoSuggestions.length} Matches (>80%)`}
                  </button>
                )}
              </div>
            </div>

            {/* Suggestions Preview Tray */}
            {autoSuggestions.length > 0 && (
              <div className="mt-4 border-t border-blue-200/80 pt-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-blue-gray-800 uppercase tracking-wide">
                    Pending Automated Suggestions ({autoSuggestions.length} found)
                  </span>
                  <button
                    type="button"
                    onClick={() => setAutoSuggestions([])}
                    className="text-xs text-blue-gray-500 hover:text-blue-gray-800 font-semibold"
                  >
                    Dismiss Suggestions Tray
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5 max-h-60 overflow-y-auto p-1">
                  {autoSuggestions.slice(0, 30).map((sugg, idx) => (
                    <div
                      key={idx}
                      className="rounded-xl border border-blue-gray-200 bg-white p-3 shadow-xs flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between gap-1 mb-1">
                          <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded border ${getPlatformBadge(sugg.marketplace_name)}`}>
                            {sugg.marketplace_name}
                          </span>
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-green-100 text-green-800 border border-green-300">
                            {sugg.confidence_percent}% Match
                          </span>
                        </div>
                        <p className="text-xs font-bold text-blue-gray-900 truncate" title={sugg.business_subcategory_name}>
                          {sugg.business_category_name} &gt; {sugg.business_subcategory_name}
                        </p>
                        <p className="mt-1 text-[11px] text-blue-gray-600 line-clamp-2" title={sugg.category_path}>
                          &bull; {sugg.category_path}
                        </p>
                      </div>
                      <div className="mt-2 pt-2 border-t border-blue-gray-100 flex justify-end">
                        <button
                          type="button"
                          onClick={() => handleApproveSingleSuggestion(sugg)}
                          className="rounded bg-blue-600 px-2.5 py-1 text-[11px] font-bold text-white hover:bg-blue-700 transition"
                        >
                          ✓ Approve
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>

          {/* Filter Bar */}
          <div className="rounded-xl border border-blue-gray-100 bg-white p-4 shadow-sm">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
              <form onSubmit={handleReportSearch} className="flex flex-1 gap-2">
                <input
                  type="search"
                  value={bpSearchInput}
                  onChange={(e) => setBpSearchInput(e.target.value)}
                  placeholder="Search by business category, subcategory, or product path..."
                  className="min-w-0 flex-1 rounded-lg border border-blue-gray-200 px-3.5 py-2 text-xs outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
                <button
                  type="submit"
                  className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-700"
                >
                  Search
                </button>
              </form>

              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={bpBusinessFilter}
                  onChange={(e) => handleBusinessFilterChange(e.target.value)}
                  className="rounded-lg border border-blue-gray-200 bg-white px-3 py-2 text-xs font-medium text-blue-gray-800"
                >
                  <option value="">All Business Categories</option>
                  {businessOptions.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>

                <select
                  value={bpMarketplaceFilter}
                  onChange={(e) => handleMarketplaceFilterChange(e.target.value)}
                  className="rounded-lg border border-blue-gray-200 bg-white px-3 py-2 text-xs font-medium text-blue-gray-800"
                >
                  <option value="">All Marketplaces (8 Platforms)</option>
                  {PLATFORMS_LIST.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>

                {(bpSearch || bpBusinessFilter || bpMarketplaceFilter) && (
                  <button
                    type="button"
                    onClick={() => {
                      setBpSearch("");
                      setBpSearchInput("");
                      setBpBusinessFilter("");
                      setBpMarketplaceFilter("");
                      loadBpMappings(1, "", "", "");
                    }}
                    className="rounded-lg border border-red-200 bg-red-50 px-2.5 py-2 text-xs font-bold text-red-700 hover:bg-red-100"
                  >
                    Clear Filters
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Mappings Matrix Table */}
          <div className="rounded-xl border border-blue-gray-100 bg-white shadow-sm overflow-hidden">
            <div className="border-b border-blue-gray-100 px-5 py-3.5 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm text-blue-gray-900">
                  Approved Business-to-Product Mapping Matrix
                </h3>
                <p className="text-xs text-blue-gray-500">
                  Showing {bpMappings.length} of {bpTotalCount} active relationships in database
                </p>
              </div>
              <span className="text-xs font-semibold text-blue-gray-600">
                Page {bpPage} of {bpTotalPages}
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-blue-gray-200 bg-blue-gray-50/70 text-blue-gray-700 font-bold uppercase tracking-wider text-[11px]">
                    <th className="py-3 px-4">Business Category (L1)</th>
                    <th className="py-3 px-4">Business Subcategory (L2)</th>
                    <th className="py-3 px-4">Carried Platform</th>
                    <th className="py-3 px-4">Product Category Path</th>
                    <th className="py-3 px-4">Relationship</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Approved By</th>
                    <th className="py-3 px-4 text-center">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-blue-gray-100">
                  {bpLoading ? (
                    <tr>
                      <td colSpan={8} className="py-12 text-center text-blue-gray-500">
                        Loading mapping report...
                      </td>
                    </tr>
                  ) : bpMappings.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-12 text-center text-blue-gray-500">
                        No mapping associations match your current filter criteria. Use the "Auto-Discover Matches" button above to generate suggestions!
                      </td>
                    </tr>
                  ) : (
                    bpMappings.map((row) => (
                      <tr key={row.id} className="hover:bg-blue-50/40 transition">
                        <td className="py-3 px-4 font-bold text-blue-gray-900">
                          {row.business_category_name}
                        </td>
                        <td className="py-3 px-4 font-semibold text-blue-gray-800">
                          {row.business_subcategory_name}
                        </td>
                        <td className="py-3 px-4">
                          <span className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-extrabold border ${getPlatformBadge(row.marketplace_name)}`}>
                            {row.marketplace_name}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-blue-gray-700 max-w-md truncate" title={row.category_path}>
                          {row.category_path}
                        </td>
                        <td className="py-3 px-4">
                          <span className="text-[11px] text-blue-gray-500 font-medium">
                            carries_products
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-green-100 text-green-800 border border-green-300">
                            ✓ APPROVED
                          </span>
                        </td>
                        <td className="py-3 px-4 text-blue-gray-500 text-[11px]">
                          {row.approved_by}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <button
                            type="button"
                            onClick={() => handleDeleteMapping(row.id)}
                            className="rounded p-1 text-red-600 hover:bg-red-50 hover:text-red-800 transition"
                            title="Delete association"
                          >
                            ✕ Delete
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="border-t border-blue-gray-100 p-3.5 flex items-center justify-between text-xs text-blue-gray-600">
              <button
                type="button"
                onClick={() => loadBpMappings(bpPage - 1, bpSearch, bpBusinessFilter, bpMarketplaceFilter)}
                disabled={bpLoading || bpPage <= 1}
                className="rounded border border-blue-gray-200 px-3 py-1.5 font-bold disabled:opacity-40"
              >
                &larr; Previous
              </button>
              <span>
                Page {bpPage} of {bpTotalPages} &bull; {bpTotalCount} Total Relationships
              </span>
              <button
                type="button"
                onClick={() => loadBpMappings(bpPage + 1, bpSearch, bpBusinessFilter, bpMarketplaceFilter)}
                disabled={bpLoading || bpPage >= bpTotalPages}
                className="rounded border border-blue-gray-200 px-3 py-1.5 font-bold disabled:opacity-40"
              >
                Next →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════
          TAB 2: INTERACTIVE 3-PANE CATEGORY MAPPER
      ═════════════════════════════════════════════════════════════════ */}
      {activeTab === "mapper" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            {/* PANE 1: SOURCE CATEGORIES */}
            <section
              aria-label="Source categories"
              className="flex min-h-[34rem] flex-col rounded-xl border border-blue-gray-100 bg-white shadow-sm"
            >
              <div className="border-b border-blue-gray-100 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="font-bold text-sm text-blue-gray-900">
                      1. Source Categories
                    </h2>
                    <p className="mt-0.5 text-xs text-blue-gray-500">
                      {sourceTotalCount.toLocaleString()} categories found
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => loadSources(sourcePage, sourceSearch, sourceStatusFilter, sourcePlatformFilter)}
                    disabled={sourceLoading}
                    className="rounded-md border border-blue-gray-200 px-2.5 py-1.5 text-xs font-semibold text-blue-gray-700 hover:bg-blue-gray-50 disabled:opacity-50"
                  >
                    Refresh
                  </button>
                </div>

                {/* Filters */}
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <select
                    value={sourcePlatformFilter}
                    onChange={(e) => handleSourcePlatformChange(e.target.value)}
                    className="rounded-md border border-blue-gray-200 bg-white px-2.5 py-1.5 text-xs font-medium text-blue-gray-800"
                  >
                    <option value="">All Platforms</option>
                    {PLATFORMS_LIST.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>

                  <select
                    value={sourceStatusFilter}
                    onChange={(e) => handleSourceStatusChange(e.target.value)}
                    className="rounded-md border border-blue-gray-200 bg-white px-2.5 py-1.5 text-xs font-medium text-blue-gray-800"
                  >
                    <option value="all">All Statuses (2,868)</option>
                    <option value="auto_mapped">Auto-Mapped / Pending Review (255)</option>
                    <option value="manually_mapped">Manually Mapped (2,613)</option>
                    <option value="unmapped">Unmapped (0)</option>
                  </select>
                </div>

                <form onSubmit={handleSourceSearch} className="mt-2.5 flex gap-2">
                  <input
                    type="search"
                    value={sourceSearchInput}
                    onChange={(event) => setSourceSearchInput(event.target.value)}
                    maxLength={255}
                    placeholder="Search raw category..."
                    className="min-w-0 flex-1 rounded-md border border-blue-gray-200 px-3 py-1.5 text-xs outline-none focus:border-blue-500"
                  />
                  <button
                    type="submit"
                    className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700"
                  >
                    Search
                  </button>
                </form>
              </div>

              {sourceError && (
                <p role="alert" className="m-4 rounded-md bg-red-50 p-3 text-xs text-red-700">
                  {sourceError}
                </p>
              )}
              <div className="flex-1 overflow-y-auto p-3">
                {sourceLoading ? (
                  <p className="p-3 text-xs text-blue-gray-500">Loading source categories...</p>
                ) : sourceRows.length === 0 ? (
                  !sourceError && (
                    <p className="p-3 text-xs text-blue-gray-500">
                      No categories match this status/platform filter.
                    </p>
                  )
                ) : (
                  <ul className="space-y-2">
                    {sourceRows.map((row) => {
                      const suggestion = autoMapResults[row.id];
                      const candidate = suggestion?.candidates?.[0];
                      const active = selectedSource?.id === row.id;
                      return (
                        <li key={row.id}>
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedSource(row);
                              setSelectedBusinessId("");
                              setSelectedSubcategoryId("");
                              setSelectedProductIds([]);
                            }}
                            className={`w-full rounded-lg border p-3 text-left transition ${
                              active
                                ? "border-blue-500 bg-blue-50 ring-1 ring-blue-200"
                                : "border-blue-gray-100 hover:border-blue-gray-300 hover:bg-blue-gray-50"
                            }`}
                          >
                            <div className="flex items-center justify-between gap-1 mb-1">
                              <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${getPlatformBadge(row.platform_name)}`}>
                                {row.platform_name}
                              </span>
                              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                row.mapping_status === "MANUALLY_MAPPED"
                                  ? "bg-green-100 text-green-800"
                                  : row.mapping_status === "AUTO_MAPPED"
                                    ? "bg-amber-100 text-amber-800"
                                    : "bg-gray-100 text-gray-700"
                              }`}>
                                {row.mapping_status}
                              </span>
                            </div>
                            <span className="block font-bold text-xs text-blue-gray-900">
                              {row.platform_category_raw}
                            </span>
                            {row.platform_subcategory_raw && (
                              <span className="mt-0.5 block text-xs text-blue-gray-600">
                                {row.platform_subcategory_raw}
                              </span>
                            )}
                          </button>
                          {candidate && (
                            <div className="mx-1 mt-1 flex items-center justify-between gap-2 rounded-md bg-amber-50 px-2 py-1.5 text-xs text-amber-900">
                              <span className="min-w-0 truncate text-[11px]">
                                Suggestion: {candidate.path} ({candidate.score_percent}%)
                              </span>
                              <button
                                type="button"
                                onClick={() => {
                                  setSelectedSource(row);
                                  chooseSuggestion(suggestion);
                                }}
                                className="shrink-0 font-bold underline"
                              >
                                Use
                              </button>
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
              <div className="flex items-center justify-between border-t border-blue-gray-100 p-3 text-xs text-blue-gray-600">
                <button
                  type="button"
                  onClick={() => loadSources(sourcePage - 1, sourceSearch, sourceStatusFilter, sourcePlatformFilter)}
                  disabled={sourceLoading || sourcePage <= 1}
                  className="rounded border border-blue-gray-200 px-2 py-1 font-semibold disabled:opacity-40"
                >
                  Prev
                </button>
                <span>
                  Page {sourcePage} of {sourceTotalPages}
                </span>
                <button
                  type="button"
                  onClick={() => loadSources(sourcePage + 1, sourceSearch, sourceStatusFilter, sourcePlatformFilter)}
                  disabled={sourceLoading || sourcePage >= sourceTotalPages}
                  className="rounded border border-blue-gray-200 px-2 py-1 font-semibold disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </section>

            {/* PANE 2: MASTER BUSINESS CATEGORY */}
            <section
              aria-label="Master business category"
              className="flex flex-col justify-between rounded-xl border border-blue-gray-100 bg-white p-4 shadow-sm"
            >
              <div>
                <h2 className="font-bold text-sm text-blue-gray-900">
                  2. Master Business Category
                </h2>
                <p className="mt-1 text-xs text-blue-gray-500">
                  Choose a level-1 business directory category and its level-2 subcategory.
                </p>

                {businessCategoriesError && (
                  <p role="alert" className="mt-3 rounded-md bg-red-50 p-2.5 text-xs text-red-700">
                    {businessCategoriesError}
                  </p>
                )}

                <label className="mt-4 block text-xs font-bold text-blue-gray-800">
                  Level 1: Business Category
                  <select
                    value={selectedBusinessId}
                    onChange={(event) => {
                      setSelectedBusinessId(event.target.value);
                      setSelectedSubcategoryId("");
                    }}
                    disabled={businessCategoriesLoading || businessOptions.length === 0}
                    className="mt-1.5 block w-full rounded-md border border-blue-gray-200 bg-white px-3 py-2 text-xs"
                  >
                    <option value="">
                      {businessCategoriesLoading
                        ? "Loading categories..."
                        : "-- Select a Business Category --"}
                    </option>
                    {businessOptions.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="mt-3.5 block text-xs font-bold text-blue-gray-800">
                  Level 2: Business Subcategory
                  <select
                    value={selectedSubcategoryId}
                    onChange={(event) => setSelectedSubcategoryId(event.target.value)}
                    disabled={!selectedBusinessId || subcategoryOptions.length === 0}
                    className="mt-1.5 block w-full rounded-md border border-blue-gray-200 bg-white px-3 py-2 text-xs"
                  >
                    <option value="">-- Select a Subcategory --</option>
                    {subcategoryOptions.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                </label>

                {selectedSource && (
                  <div className="mt-5 rounded-lg border border-blue-100 bg-blue-50/60 p-3">
                    <p className="text-[10px] font-extrabold uppercase tracking-wide text-blue-600">
                      Currently Selected Source Category:
                    </p>
                    <p className="mt-1 font-bold text-xs text-blue-gray-900">
                      {selectedSource.platform_category_raw}
                    </p>
                    <p className="text-[11px] text-blue-gray-600">
                      Platform: <strong>{selectedSource.platform_name}</strong>
                      {selectedSource.platform_subcategory_raw
                        ? ` &bull; ${selectedSource.platform_subcategory_raw}`
                        : ""}
                    </p>
                  </div>
                )}
              </div>

              {autoMapSummary && (
                <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-950">
                  Auto-map previewed {autoMapSummary.data?.length || 0} candidates. Manual approval persists them with 100% confidence.
                </div>
              )}
            </section>

            {/* PANE 3: PRODUCT CATEGORIES */}
            <section
              aria-label="Product categories"
              className="flex min-h-[34rem] flex-col rounded-xl border border-blue-gray-100 bg-white shadow-sm"
            >
              <div className="border-b border-blue-gray-100 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="font-bold text-sm text-blue-gray-900">
                      3. Carried Product Categories
                    </h2>
                    <p className="mt-0.5 text-xs text-blue-gray-500">
                      {selectedProductIds.length} categories selected (All 8 platforms)
                    </p>
                  </div>
                  <span className="rounded-full bg-blue-gray-100 px-2.5 py-1 text-[11px] font-bold text-blue-gray-700">
                    Max {MAX_PRODUCT_SELECTION}
                  </span>
                </div>

                {/* Marketplace Filter */}
                <div className="mt-3">
                  <select
                    value={productMarketplaceFilter}
                    onChange={(e) => handleProductMarketplaceChange(e.target.value)}
                    className="w-full rounded-md border border-blue-gray-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-blue-gray-800"
                  >
                    <option value="">All Marketplaces (4,898 Categories)</option>
                    {PLATFORMS_LIST.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </div>

                <form onSubmit={handleProductSearch} className="mt-2.5 flex gap-2">
                  <input
                    type="search"
                    value={productSearchInput}
                    onChange={(event) => setProductSearchInput(event.target.value)}
                    maxLength={255}
                    placeholder="Search product categories..."
                    className="min-w-0 flex-1 rounded-md border border-blue-gray-200 px-3 py-1.5 text-xs outline-none focus:border-blue-500"
                  />
                  <button
                    type="submit"
                    className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700"
                  >
                    Search
                  </button>
                </form>
              </div>

              {selectedProducts.length > 0 && (
                <div className="flex flex-wrap gap-1.5 border-b border-blue-gray-100 p-2.5 max-h-24 overflow-y-auto">
                  {selectedProducts.map((category) => (
                    <button
                      key={category.id}
                      type="button"
                      onClick={() => toggleProduct(category)}
                      className="max-w-full truncate rounded-full bg-blue-100 px-2.5 py-0.5 text-[10px] font-bold text-blue-800 hover:bg-blue-200"
                    >
                      {category.marketplace_name}: {category.category_name} ✕
                    </button>
                  ))}
                </div>
              )}

              {productError && (
                <p role="alert" className="m-4 rounded-md bg-red-50 p-3 text-xs text-red-700">
                  {productError}
                </p>
              )}

              <div className="flex-1 overflow-y-auto p-3">
                {productLoading ? (
                  <p className="p-3 text-xs text-blue-gray-500">Loading product categories...</p>
                ) : productCategories.length === 0 ? (
                  !productError && (
                    <p className="p-3 text-xs text-blue-gray-500">
                      No product categories match this search or marketplace.
                    </p>
                  )
                ) : (
                  <ul className="space-y-1">
                    {productCategories.map((category) => (
                      <li key={category.id}>
                        <label className="flex cursor-pointer items-start gap-2.5 rounded-md px-2 py-1.5 hover:bg-blue-gray-50">
                          <input
                            type="checkbox"
                            checked={selectedProductIds.includes(category.id)}
                            onChange={() => toggleProduct(category)}
                            className="mt-0.5 h-3.5 w-3.5 rounded border-blue-gray-300 text-blue-600"
                          />
                          <span className="min-w-0">
                            <span className="block text-xs font-bold text-blue-gray-900">
                              {getProductPath(category)}
                            </span>
                            <span className="block text-[10px] font-semibold text-blue-gray-500">
                              {category.marketplace_name} &bull; Level {category.category_level}
                            </span>
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="flex items-center justify-between border-t border-blue-gray-100 p-3 text-xs text-blue-gray-600">
                <button
                  type="button"
                  onClick={() => loadProducts(productPage - 1, productSearch, productMarketplaceFilter)}
                  disabled={productLoading || productPage <= 1}
                  className="rounded border border-blue-gray-200 px-2 py-1 font-semibold disabled:opacity-40"
                >
                  Prev
                </button>
                <span>
                  Page {productPage} of {productTotalPages}
                </span>
                <button
                  type="button"
                  onClick={() => loadProducts(productPage + 1, productSearch, productMarketplaceFilter)}
                  disabled={productLoading || productPage >= productTotalPages}
                  className="rounded border border-blue-gray-200 px-2 py-1 font-semibold disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </section>
          </div>

          {/* Bottom Review & Approval Bar */}
          <section className="rounded-xl border border-blue-gray-100 bg-white p-4 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h3 className="font-bold text-sm text-blue-gray-900">
                Review and Persist Mapping
              </h3>
              <p className="text-xs text-blue-gray-600">
                Associates selected source category to the business subcategory, and stores carried product catalog relationships in the reviewed PostgreSQL schema.
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={runAutoMap}
                disabled={autoMapLoading || sourceRows.length === 0}
                className="rounded-lg border border-amber-300 bg-amber-50 px-3.5 py-2 text-xs font-bold text-amber-900 hover:bg-amber-100 disabled:opacity-50"
              >
                {autoMapLoading ? "Evaluating..." : "Auto-Map (80%+ Preview)"}
              </button>
              <button
                type="button"
                onClick={approveMapping}
                disabled={!canApprove}
                className="rounded-lg bg-green-600 px-4 py-2 text-xs font-bold text-white hover:bg-green-700 disabled:opacity-50 shadow"
              >
                {saving ? "Saving..." : "✓ Approve Mapping"}
              </button>
            </div>
          </section>
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════
          TAB 3: PLATFORM COVERAGE BREAKDOWN
      ═════════════════════════════════════════════════════════════════ */}
      {activeTab === "analytics" && (
        <div className="space-y-6">
          <div className="rounded-xl border border-blue-gray-100 bg-white p-5 shadow-sm">
            <h3 className="text-base font-bold text-blue-gray-900">
              Platform Catalog Breakdown (8 E-Commerce Platforms)
            </h3>
            <p className="mt-1 text-xs text-blue-gray-600">
              Live statistics showing total categories extracted per marketplace and the volume of products currently mapped to CityHangaround business listings.
            </p>

            {bpStats?.platforms && (
              <div className="mt-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {bpStats.platforms.map((p) => (
                  <div
                    key={p.platform}
                    className="rounded-xl border border-blue-gray-200 bg-white p-4 shadow-xs hover:shadow-md transition"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span className={`text-xs font-extrabold px-2.5 py-0.5 rounded-full border ${getPlatformBadge(p.platform)}`}>
                        {p.platform}
                      </span>
                      <span className="text-xs font-bold text-blue-gray-900">
                        {p.total.toLocaleString()} total
                      </span>
                    </div>

                    <div className="space-y-1.5 text-xs text-blue-gray-600">
                      <div className="flex justify-between">
                        <span>Mapped in DB:</span>
                        <span className="font-bold text-green-700">{p.mapped}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Coverage:</span>
                        <span className="font-bold text-blue-600">{p.percent_mapped}%</span>
                      </div>
                    </div>

                    {/* Progress Bar */}
                    <div className="mt-3.5 w-full bg-blue-gray-100 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-blue-600 h-1.5 rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(100, Math.max(5, p.percent_mapped))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </main>
  );
}

export default CategoryMapper;
