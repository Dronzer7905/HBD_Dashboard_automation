import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../../configs/api";

const SOURCE_PAGE_SIZE = 50;
const CATEGORY_PAGE_SIZE = 200;
const PRODUCT_PAGE_SIZE = 50;
const MAX_PRODUCT_SELECTION = 100;

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
  const [sourceRows, setSourceRows] = useState([]);
  const [sourcePage, setSourcePage] = useState(1);
  const [sourceTotalPages, setSourceTotalPages] = useState(1);
  const [sourceTotalCount, setSourceTotalCount] = useState(0);
  const [sourceSearchInput, setSourceSearchInput] = useState("");
  const [sourceSearch, setSourceSearch] = useState("");
  const [sourceLoading, setSourceLoading] = useState(true);
  const [sourceError, setSourceError] = useState("");
  const [selectedSource, setSelectedSource] = useState(null);

  const [businessCategories, setBusinessCategories] = useState([]);
  const [businessCategoriesLoading, setBusinessCategoriesLoading] =
    useState(true);
  const [businessCategoriesError, setBusinessCategoriesError] = useState("");
  const [selectedBusinessId, setSelectedBusinessId] = useState("");
  const [selectedSubcategoryId, setSelectedSubcategoryId] = useState("");

  const [productCategories, setProductCategories] = useState([]);
  const [productLookup, setProductLookup] = useState({});
  const [productPage, setProductPage] = useState(1);
  const [productTotalPages, setProductTotalPages] = useState(1);
  const [productSearchInput, setProductSearchInput] = useState("");
  const [productSearch, setProductSearch] = useState("");
  const [productLoading, setProductLoading] = useState(true);
  const [productError, setProductError] = useState("");
  const [selectedProductIds, setSelectedProductIds] = useState([]);

  const [capabilities, setCapabilities] = useState(null);
  const [autoMapLoading, setAutoMapLoading] = useState(false);
  const [autoMapResults, setAutoMapResults] = useState({});
  const [autoMapSummary, setAutoMapSummary] = useState(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  const loadSources = useCallback(async (page, search) => {
    setSourceLoading(true);
    setSourceError("");
    try {
      const params = {
        status: "unmapped",
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
      setSourceError(getErrorMessage(error, "Unable to load unmapped categories."));
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
            status: "unmapped",
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
      const totalPages = firstPage.total_pages || 1;
      for (let page = 2; page <= totalPages; page += 1) {
        const payload = getPayload(
          await api.get("/mapping/categories", {
            params: {
              status: "unmapped",
              limit: 1,
              category_page: page,
              category_limit: CATEGORY_PAGE_SIZE,
              product_limit: 1,
            },
          }),
        );
        if (!Array.isArray(payload.canonical_categories?.data)) {
          throw new Error("A master category page is missing from the API response.");
        }
        pages.push(payload.canonical_categories.data);
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

  const loadProducts = useCallback(async (page, search) => {
    setProductLoading(true);
    setProductError("");
    try {
      const payload = getPayload(
        await api.get("/mapping/categories", {
          params: {
            status: "unmapped",
            limit: 1,
            category_limit: 1,
            product_page: page,
            product_limit: PRODUCT_PAGE_SIZE,
            product_search: search || undefined,
          },
        }),
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

  useEffect(() => {
    loadSources(1, "");
    loadBusinessCategories();
    loadProducts(1, "");
  }, [loadSources, loadBusinessCategories, loadProducts]);

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

  const handleSourceSearch = (event) => {
    event.preventDefault();
    const search = sourceSearchInput.trim();
    setSourceSearch(search);
    setSourcePage(1);
    loadSources(1, search);
  };

  const handleProductSearch = (event) => {
    event.preventDefault();
    const search = productSearchInput.trim();
    setProductSearch(search);
    loadProducts(1, search);
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
      text: "Suggestion selected for review. It is not approved until you submit the mapping.",
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
        throw new Error(
          payload?.message || "The auto-map API returned an invalid response.",
        );
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
        text: `Mapping approved. ${associationCount} product association(s) added.`,
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
      await loadSources(sourcePage, sourceSearch);
    } catch (error) {
      const details = getErrorMessage(error, "The mapping request failed.");
      setMessage({
        type: "error",
        text: associationsSaved
          ? `Product associations were saved, but the source category mapping failed: ${details}. You can retry the source mapping; duplicate product associations are ignored by the API.`
          : details,
      });
    } finally {
      setSaving(false);
    }
  };

  const capabilitiesReady = capabilities !== null;
  const associationsEnabled =
    capabilities?.business_product_associations === true;
  const canApprove =
    Boolean(selectedSource) &&
    Boolean(selectedBusinessId) &&
    Boolean(selectedSubcategoryId) &&
    selectedProductIds.length > 0 &&
    associationsEnabled &&
    !saving;

  return (
    <main className="min-h-screen bg-blue-gray-50/50 p-4 md:p-6">
      <header className="mb-6">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-blue-600">
          Category &amp; Catalog Mapping
        </p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-blue-gray-900">
              Business-to-Product Category Mapper
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-blue-gray-600">
              Review raw source categories, assign a master business
              subcategory, and choose the product categories it carries.
            </p>
          </div>
          <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-bold text-blue-800">
            AR-1.7
          </span>
        </div>
      </header>

      <StatusMessage
        message={message}
        onDismiss={() => setMessage(null)}
      />

      <div className="mb-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <section
          aria-label="Unmapped source categories"
          className="flex min-h-[32rem] flex-col rounded-xl border border-blue-gray-100 bg-white shadow-sm"
        >
          <div className="border-b border-blue-gray-100 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold text-blue-gray-900">
                  Unmapped source categories
                </h2>
                <p className="mt-1 text-xs text-blue-gray-500">
                  {sourceTotalCount.toLocaleString()} pending
                </p>
              </div>
              <button
                type="button"
                onClick={() => loadSources(sourcePage, sourceSearch)}
                disabled={sourceLoading}
                className="rounded-md border border-blue-gray-200 px-3 py-2 text-xs font-semibold text-blue-gray-700 hover:bg-blue-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Refresh
              </button>
            </div>
            <form onSubmit={handleSourceSearch} className="mt-3 flex gap-2">
              <input
                type="search"
                value={sourceSearchInput}
                onChange={(event) => setSourceSearchInput(event.target.value)}
                maxLength={255}
                placeholder="Search raw category or subcategory"
                aria-label="Search source categories"
                className="min-w-0 flex-1 rounded-md border border-blue-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              />
              <button
                type="submit"
                className="rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              >
                Search
              </button>
            </form>
          </div>

          {sourceError && (
            <p role="alert" className="m-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
              {sourceError}
            </p>
          )}
          <div className="flex-1 overflow-y-auto p-3">
            {sourceLoading ? (
              <p className="p-3 text-sm text-blue-gray-500" role="status">
                Loading source categories...
              </p>
            ) : sourceRows.length === 0 ? (
              !sourceError && (
                <p className="p-3 text-sm text-blue-gray-500">
                  No unmapped categories match this search.
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
                        aria-pressed={active}
                        className={`w-full rounded-lg border p-3 text-left transition ${
                          active
                            ? "border-blue-500 bg-blue-50 ring-1 ring-blue-200"
                            : "border-blue-gray-100 hover:border-blue-gray-300 hover:bg-blue-gray-50"
                        }`}
                      >
                        <span className="block font-semibold text-blue-gray-900">
                          {row.platform_category_raw}
                        </span>
                        {row.platform_subcategory_raw && (
                          <span className="mt-1 block text-sm text-blue-gray-600">
                            {row.platform_subcategory_raw}
                          </span>
                        )}
                        <span className="mt-2 flex flex-wrap items-center gap-2 text-xs text-blue-gray-500">
                          <span>{row.platform_name}</span>
                          <span aria-hidden="true">&bull;</span>
                          <span>{row.mapping_status}</span>
                        </span>
                      </button>
                      {candidate && (
                        <div className="mx-1 mt-1 flex items-center justify-between gap-2 rounded-md bg-amber-50 px-2 py-1.5 text-xs text-amber-900">
                          <span className="min-w-0 truncate">
                            Suggestion: {candidate.path} (
                            {candidate.score_percent}%)
                            {suggestion.classification === "ambiguous" &&
                              " - ambiguous"}
                          </span>
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedSource(row);
                              chooseSuggestion(suggestion);
                            }}
                            disabled={suggestion.classification === "ambiguous"}
                            className="shrink-0 font-semibold underline disabled:cursor-not-allowed disabled:opacity-50"
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
              onClick={() => loadSources(sourcePage - 1, sourceSearch)}
              disabled={sourceLoading || sourcePage <= 1}
              className="rounded border border-blue-gray-200 px-2 py-1.5 font-semibold disabled:cursor-not-allowed disabled:opacity-40"
            >
              Previous
            </button>
            <span>
              Page {sourcePage} of {sourceTotalPages}
            </span>
            <button
              type="button"
              onClick={() => loadSources(sourcePage + 1, sourceSearch)}
              disabled={sourceLoading || sourcePage >= sourceTotalPages}
              className="rounded border border-blue-gray-200 px-2 py-1.5 font-semibold disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </section>

        <section
          aria-label="Master business category"
          className="rounded-xl border border-blue-gray-100 bg-white p-4 shadow-sm"
        >
          <h2 className="font-semibold text-blue-gray-900">
            Master business category
          </h2>
          <p className="mt-1 text-sm text-blue-gray-500">
            Choose a level-one business category and its direct subcategory.
          </p>

          {businessCategoriesError && (
            <p role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
              {businessCategoriesError}
            </p>
          )}
          <label className="mt-5 block text-sm font-medium text-blue-gray-800">
            Business category
            <select
              value={selectedBusinessId}
              onChange={(event) => {
                setSelectedBusinessId(event.target.value);
                setSelectedSubcategoryId("");
              }}
              disabled={businessCategoriesLoading || businessOptions.length === 0}
              className="mt-2 block w-full rounded-md border border-blue-gray-200 bg-white px-3 py-2.5 text-sm disabled:bg-blue-gray-50"
            >
              <option value="">
                {businessCategoriesLoading
                  ? "Loading categories..."
                  : "Select a business category"}
              </option>
              {businessOptions.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>

          <label className="mt-4 block text-sm font-medium text-blue-gray-800">
            Business subcategory
            <select
              value={selectedSubcategoryId}
              onChange={(event) => setSelectedSubcategoryId(event.target.value)}
              disabled={!selectedBusinessId || subcategoryOptions.length === 0}
              className="mt-2 block w-full rounded-md border border-blue-gray-200 bg-white px-3 py-2.5 text-sm disabled:bg-blue-gray-50"
            >
              <option value="">Select a subcategory</option>
              {subcategoryOptions.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>

          {selectedSource && (
            <div className="mt-6 rounded-lg border border-blue-gray-100 bg-blue-gray-50 p-3">
              <p className="text-xs font-bold uppercase tracking-wide text-blue-gray-500">
                Mapping source
              </p>
              <p className="mt-1 font-semibold text-blue-gray-900">
                {selectedSource.platform_category_raw}
              </p>
              <p className="text-sm text-blue-gray-600">
                {selectedSource.platform_name}
                {selectedSource.platform_subcategory_raw
                  ? ` / ${selectedSource.platform_subcategory_raw}`
                  : ""}
              </p>
            </div>
          )}

          {autoMapSummary && (
            <div className="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
              Auto-map is a preview only. The backend requires at least 90%
              confidence plus admin authorization for automatic persistence.
              Suggestions at 80% or higher still require manual approval.
            </div>
          )}
        </section>

        <section
          aria-label="Product categories"
          className="flex min-h-[32rem] flex-col rounded-xl border border-blue-gray-100 bg-white shadow-sm"
        >
          <div className="border-b border-blue-gray-100 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold text-blue-gray-900">
                  Product categories
                </h2>
                <p className="mt-1 text-xs text-blue-gray-500">
                  {selectedProductIds.length} selected
                </p>
              </div>
              <span className="rounded-full bg-blue-gray-100 px-2.5 py-1 text-xs font-medium text-blue-gray-700">
                Up to {MAX_PRODUCT_SELECTION}
              </span>
            </div>
            <form onSubmit={handleProductSearch} className="mt-3 flex gap-2">
              <input
                type="search"
                value={productSearchInput}
                onChange={(event) => setProductSearchInput(event.target.value)}
                maxLength={255}
                placeholder="Search product category"
                aria-label="Search product categories"
                className="min-w-0 flex-1 rounded-md border border-blue-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              />
              <button
                type="submit"
                className="rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              >
                Search
              </button>
            </form>
          </div>

          {selectedProducts.length > 0 && (
            <div className="flex flex-wrap gap-2 border-b border-blue-gray-100 p-3">
              {selectedProducts.map((category) => (
                <button
                  key={category.id}
                  type="button"
                  onClick={() => toggleProduct(category)}
                  aria-label={`Remove ${getProductPath(category)}`}
                  className="max-w-full truncate rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-800 hover:bg-blue-200"
                >
                  {getProductPath(category)} &times;
                </button>
              ))}
            </div>
          )}

          {productError && (
            <p role="alert" className="m-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
              {productError}
            </p>
          )}
          <div className="flex-1 overflow-y-auto p-3">
            {productLoading ? (
              <p className="p-3 text-sm text-blue-gray-500" role="status">
                Loading product categories...
              </p>
            ) : productCategories.length === 0 ? (
              !productError && (
                <p className="p-3 text-sm text-blue-gray-500">
                  No product categories match this search.
                </p>
              )
            ) : (
              <ul className="space-y-1">
                {productCategories.map((category) => (
                  <li key={category.id}>
                    <label className="flex cursor-pointer items-start gap-3 rounded-md px-2 py-2 hover:bg-blue-gray-50">
                      <input
                        type="checkbox"
                        checked={selectedProductIds.includes(category.id)}
                        onChange={() => toggleProduct(category)}
                        className="mt-0.5 h-4 w-4 rounded border-blue-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="min-w-0">
                        <span className="block text-sm font-medium text-blue-gray-900">
                          {getProductPath(category)}
                        </span>
                        <span className="block text-xs text-blue-gray-500">
                          {category.marketplace_name}
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
              onClick={() => loadProducts(productPage - 1, productSearch)}
              disabled={productLoading || productPage <= 1}
              className="rounded border border-blue-gray-200 px-2 py-1.5 font-semibold disabled:cursor-not-allowed disabled:opacity-40"
            >
              Previous
            </button>
            <span>
              Page {productPage} of {productTotalPages}
            </span>
            <button
              type="button"
              onClick={() => loadProducts(productPage + 1, productSearch)}
              disabled={productLoading || productPage >= productTotalPages}
              className="rounded border border-blue-gray-200 px-2 py-1.5 font-semibold disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </section>
      </div>

      <section className="rounded-xl border border-blue-gray-100 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="font-semibold text-blue-gray-900">
              Review and approve
            </h2>
            <p className="mt-1 max-w-3xl text-sm text-blue-gray-600">
              Approval creates the product associations, then maps the selected
              source category to the chosen business subcategory. These are
              separate backend transactions; if the second request fails, the
              saved product associations remain and can be safely retried.
            </p>
            {capabilitiesReady && !associationsEnabled && (
              <p role="alert" className="mt-2 text-sm font-medium text-amber-800">
                Product association storage is disabled by the backend. Approval
                is unavailable until an approved storage capability is enabled.
              </p>
            )}
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <button
              type="button"
              onClick={runAutoMap}
              disabled={autoMapLoading || sourceRows.length === 0}
              className="rounded-md border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm font-semibold text-amber-900 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {autoMapLoading ? "Finding suggestions..." : "Auto-Map (80%+ preview)"}
            </button>
            <button
              type="button"
              onClick={approveMapping}
              disabled={!canApprove}
              className="rounded-md bg-green-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Saving..." : "Approve mapping"}
            </button>
          </div>
        </div>

        {autoMapSummary && (
          <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 rounded-lg bg-blue-gray-50 px-3 py-2 text-sm text-blue-gray-700">
            <span>
              Previewed: <strong>{autoMapSummary.data.length}</strong>
            </span>
            <span>
              Threshold: <strong>{Math.round(autoMapSummary.threshold * 100)}%</strong>
            </span>
            <span>
              More available: <strong>{autoMapSummary.has_more ? "Yes" : "No"}</strong>
            </span>
            {autoMapSummary.summary && (
              <span>
                Ambiguous: <strong>{autoMapSummary.summary.ambiguous}</strong>
              </span>
            )}
          </div>
        )}
      </section>
    </main>
  );
}

export default CategoryMapper;
