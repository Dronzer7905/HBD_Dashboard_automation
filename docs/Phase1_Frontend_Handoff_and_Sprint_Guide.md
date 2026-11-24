# Phase 1 Frontend Handoff & Developer Guide
**Assignee**: Anusha Ronda (Frontend Lead)  
**Project**: CityHangaround (`HBD_Dashboard_automation`)  
**Current Branch**: `lead/phase1-nav-reorganization`  
**Status**: Ready for Implementation  
**Last Build Verification**: `npm run build` passed with **0 errors** (2,073 modules compiled).

---

## 1. Executive Summary

This document outlines the current state of the frontend application following the architectural consolidation. 

All previously functioning routes (Master Data, Clean Data, Product Catalogs, HBD Reports, Data Enrichment, Scrapers) have been **100% preserved**. The 7-section enterprise navigation structure is active and **fully dynamic**.

Use this guide to review what is already done so you **do not duplicate effort**, understand the architectural standards, and proceed directly to your immediate active task: **`AR-1.7` (Category Mapper UI)**.

---

## 2. Completed Modules Checklist (DO NOT RE-DO)

The following modules have already been implemented, connected, and verified in the production build. You do **not** need to recreate or rewrite them:

| Task ID | Module / Feature | Status | Implementation Details |
| :--- | :--- | :--- | :--- |
| **`AR-1.1`** | **Deprecate 15 Dead Routes** | **COMPLETED** | Hidden 15 obsolete scraper routes in `frontend/src/routes.jsx` with `hidden: true`. |
| **`AR-1.2`** | **7-Section Sidenav Hierarchy** | **COMPLETED** | Fully structured in `frontend/src/routes.jsx` and rendered dynamically in `frontend/src/widgets/layout/sidenav.jsx`. |
| **`AR-1.3`** | **Manager Command Center** | **UI READY** | `frontend/src/pages/admin/CommandCenter.jsx` is active. Currently displaying reference values; will automatically show live telemetry once Bhargav deploys `BG-1.13` (`/api/pipeline-status`). |
| **`AR-1.4`** | **Pipeline Status Funnel** | **UI READY** | `frontend/src/pages/reports/PipelineStatus.jsx` is active with visual 5-stage progress bars. |
| **`AR-1.5`** | **Guided Bulk Ingestion Wizard** | **UI READY** | `frontend/src/pages/ingest/GuidedIngestionWizard.jsx` contains the 5-step UI flow. Waiting only on backend file parsing API (`BG-1.8`). |
| **`AR-1.6`** | **Scraper Scheduler & Monitor** | **UI READY** | `frontend/src/pages/ingest/ScraperScheduler.jsx` card grid is active. |
| **`AR-1.9`** | **Unmatched Data Review** | **ALIGNED** | Route path mismatch resolved. Accessible at `/masterdata/unmatched-data-review` and `/dashboard/unmatched_data_review`. |
| **`AR-1.21`**| **Frontend Production Build** | **VERIFIED** | Vite compiles cleanly (`✓ built in 52s`). |
| **`AR-1.10`–`AR-1.20`** | **Placeholders Scaffolding** | **SCAFFOLDED** | All 13 pending screens across Commerce, Leisure, and Content are rendered using `ComingSoon.jsx` cards with zero 404 errors. |

---

## 3. Core Architectural Concept: Dynamic Sidenav

### The Single Source of Truth Principle
In this project, **`frontend/src/routes.jsx` is the ONLY place where routes and menu items are defined**.

```
[ frontend/src/routes.jsx ]  <--- The Single Source of Truth
             │
             ├── Loaded by App.jsx / Dashboard.jsx (for React Router)
             └── Loaded by Sidenav.jsx (for rendering the sidebar menu)
```

### Why We Never Hardcode Navigation in `sidenav.jsx`:
- **The Scalability Problem**: If `sidenav.jsx` has a static list (`const sidenavSections = [...]`), then whenever someone adds a new screen, report, or scraper in `routes.jsx`, it **never appears** in the sidebar unless they also remember to edit `sidenav.jsx`.
- **The Dynamic Solution**: `sidenav.jsx` simply maps over the `routes` prop passed to it. It reads the icons, names, and paths directly from `routes.jsx` and ignores anything marked `hidden: true`.
- **Rule of Thumb**: When creating a new screen:
  1. Create your component in `frontend/src/pages/...`.
  2. Add it to the appropriate section in `frontend/src/routes.jsx`.
  3. **Done!** The sidebar renders it automatically. Never touch `sidenav.jsx` for adding standard routes.

---

## 4. Your Immediate Active Task: `AR-1.7` (Category Mapper UI)

> **File to Implement**: `frontend/src/pages/mapping/CategoryMapper.jsx`  
> **Route**: `/dashboard/mapping/categories`  
> **Backend Status**: Bhargav’s backend APIs (`BG-1.11`) are **live and running on port 8001**. You have real endpoints to build against right now!

### Objective:
Build the 3-column Category Mapping dashboard that allows human operators and admins to map raw scraped category strings to master business categories, and associate them with multiple product categories.

```
┌───────────────────────────┬───────────────────────────┬───────────────────────────┐
│  Column 1: Raw String     │  Column 2: Business Type  │  Column 3: Product Cats   │
├───────────────────────────┼───────────────────────────┼───────────────────────────┤
│ "Fresh Mart Groceries"    │ [ Shopping > Kirana  ▼ ]  │ [x] Fresh Produce         │
│                           │                           │ [x] Dairy & Eggs          │
│                           │                           │ [x] Cooking Oils & Ghee   │
│                           │                           │ [x] Packaged Snacks       │
├───────────────────────────┴───────────────────────────┴───────────────────────────┤
│ [ Auto-Map AI (≥80%) ]                                [ Approve Mapping Button ]  │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### Specifications for the 3 Columns:

#### 1. Left Column: Unmapped Source Categories
- **API Call**: `GET /api/mapping/categories?status=unmapped&page=1&limit=50`
- **Display**: Shows raw category strings scraped from external directories (*e.g., "Organic Mart", "Sourdough Bakery", "Apollo Pharmacy"*).
- Includes search filter and pagination controls.

#### 2. Middle Column: Master Business Category Selector
- Displays a searchable dropdown containing canonical categories from `master_categories` (*e.g., "Shopping > Kirana Stores"* or *"Dining > Cafes"*).
- Displays the hierarchy breadcrumb path (`Shopping > Grocery`).

#### 3. Right Column: Product Categories Multi-Select
- Displays searchable checkboxes or a multi-select dropdown of product categories from `product_category_master` (*e.g., "Fresh Produce", "Dairy Products", "Beverages"*).
- A single business subcategory (like *Organic Store*) can carry **multiple product categories**.

#### 4. Action Buttons:
- **"Approve Mapping"**:
  - Sends a `POST /api/mapping/map-category` request.
  - **Payload**:
    ```json
    {
      "source_category_id": 1,
      "master_category_id": 2,
      "product_category_ids": [101, 102],
      "mapping_type": "carries_products"
    }
    ```
- **"Batch Auto-Map"**:
  - Sends a `POST /api/mapping/auto-map` request:
    ```json
    {
      "dry_run": true,
      "threshold": 0.80
    }
    ```
  - Displays fuzzy matching suggestions with match confidence scores (*e.g., "94% match"*).

---

## 5. What Comes Next (Phase 1 Sprint 2 Roadmap)

Once you complete `AR-1.7`, here is the sequence of upcoming work:

1. **`AR-1.8`: Attribute Standardizer (`AttributeStandardizer.jsx`)**:
   - Schema builder for category-specific attributes (*e.g., Cuisines for Restaurants, Warranties for Plumbers*).
2. **Hooking Up Telemetry & Ingestion (When Bhargav pushes APIs)**:
   - When Bhargav finishes `BG-1.13`: `CommandCenter.jsx` and `PipelineStatus.jsx` will be connected to real-time database numbers via `GET /api/pipeline-status`.
   - When Bhargav finishes `BG-1.8`: `GuidedIngestionWizard.jsx` will be connected to `POST /api/ingest/upload` for CSV file parsing.
3. **8 Vertical Archetype Presentation Screens (`AR-1.10` to `AR-1.18`)**:
   - Implementing individual management forms for Dining, Quick Commerce, Services, Healthcare, Tourism, Hotels, and Play Areas.

---

## 6. How to Run the Environment Locally

To run and test your code locally:

1. **Start the Frontend**:
   ```bash
   cd frontend
   npm run dev
   ```
   Open: `http://localhost:5173/dashboard/home` (Local dev bypass is enabled).

2. **Verify the Production Build**:
   ```bash
   cd frontend
   npm run build
   ```
   Always verify zero build errors before committing.
