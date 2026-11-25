import {
  HomeIcon,
  UserCircleIcon,
  TableCellsIcon,
  InformationCircleIcon,
  ServerStackIcon,
  RectangleStackIcon,
  MagnifyingGlassIcon,
  MapPinIcon,
  ShoppingCartIcon,
  CheckCircleIcon,
  XCircleIcon,
  DocumentTextIcon,
  ArrowUpTrayIcon,
  ChartBarIcon,
} from "@heroicons/react/24/solid";

// --- Existing working components ---
import MasterDataUploader from "./componunts/data import/MasterDataUploader";
import MasterData from "./componunts/masterdata/Masterdata";
import { Home } from "./pages/dashboard/home";
import { Profile } from "./pages/dashboard/profile";
import { Tables } from "./pages/dashboard/tables";
import { Notifications } from "./pages/dashboard/notifications";
import UnmatchedDataReview from "./pages/dashboard/unmatched_data_review";
import ZomatoData from "./componunts/product master data/ZomatoData";
import CitiesReports from "./componunts/Reports/cities_reports";
import CategoriesReports from "./componunts/Reports/categories_reports";
import CitiesPendingReport from "./componunts/Reports/CitiesPendingReport";
import CategoriesPendingReport from "./componunts/Reports/CategoriesPendingReport";
import HeyPlacesData from "./componunts/Source Wise data/HeyPlacesData.jsx";
import BankData from "./componunts/Source Wise data/BankData";
import ProductCategory from "./componunts/masterdata/ProductCategory";
import ListingComplete from "./componunts/Source Wise data/ListingComplate";
import ListingIncomplate from "./componunts/Source Wise data/ListingIncomplate";
import ProductComplete from "./componunts/product master data/ProductComplate";
import ProductIncomplate from "./componunts/product master data/ProductIncomplate";
import AmazonData from "./componunts/product master data/AmazonData";
import FlipkartData from "./componunts/product master data/FlipkartData";
import BigBasketData from "./componunts/product master data/BigBasket";
import ServiceComplate from "./componunts/service master data/ServiceComplate";
import ServiceIncomplate from "./componunts/service master data/ServiceIncomplate";
import GoogleMapScrapper from "./componunts/scrapper/GoogleMapScrapper";
import CleanListingMaster from "./componunts/clean master data/CleanListingMaster";
import CleanProductMaster from "./componunts/clean master data/CleanProductMaster";
import DataCleaningDashboard from "./componunts/clean master data/DataCleaningDashboard";
import DynamicTierDashboard from "./componunts/clean master data/DynamicTierDashboard";
import ListingCategory from "./componunts/masterdata/ListingCategory";
import ReportDashboard from "./componunts/ReportDashboard";
import AggregateReport from "./componunts/AggregateReport";
import ListingDataReport from "./componunts/ListingDataReport";
import ProductDataReport from "./componunts/ProductDataReport";
import MisReportTable from "./componunts/Misreport";
import ProductDetails from "./componunts/ProductDetails";
import AmazonScraper from "./componunts/scrapper/AmazonScrapper";
import OthersDataImport from "./componunts/data import/OthersDataImport";
import SearchKeyword from "./componunts/SearchKeyword";
import DmartScrapper from "./componunts/scrapper/DmartScrapper";
import FlipkartScrapper from "./componunts/scrapper/FlipkartScrapper";
import State from "./componunts/masterdata/location msater/State";
import Country from "./componunts/masterdata/location msater/Country";
import Area from "./componunts/masterdata/location msater/Area";
import City from "./componunts/masterdata/location msater/City";
import GoogleData from "./componunts/Source Wise data/GoogleData";
import GoogleMapData from "./componunts/Source Wise data/GoogleMapData";
import CollegeDuniaData from "./componunts/Source Wise data/CollegeDuniaData";
import MagicPinData from "./componunts/Source Wise data/MagicPinData";
import AsklailaData from "./componunts/Source Wise data/AsklailaData";
import AtmData from "./componunts/Source Wise data/AtmData";
import JustDialData from "./componunts/Source Wise data/JustDialData";
import POIndiaData from "./componunts/Source Wise data/POIndiaData";
import NearBuyData from "./componunts/Source Wise data/NearBuyData";
import SchoolgisData from "./componunts/Source Wise data/SchoolgisData";
import YellowPagesData from "./componunts/Source Wise data/YellowPagesData";
import PindaData from "./componunts/Source Wise data/PindaData";
import GoogleUploader from "./componunts/data import/listing import/GoogleUploader";
import BankDataUploader from "./componunts/data import/listing import/BankDataUploader";
import CollegeDuniaUploader from "./componunts/data import/listing import/CollegeDuniaUploader";
import HeyPlacesUploader from "./componunts/data import/listing import/HeyPlacesUploader";
import AtmUploader from "./componunts/data import/listing import/AtmUploader";
import AsklailaUploader from "./componunts/data import/listing import/AsklailaUploader";
import PindaUploader from "./componunts/data import/listing import/PindaUploader";
import YellowPagesUploader from "./componunts/data import/listing import/YellowPagesUploader";
import SchoolgisUploader from "./componunts/data import/listing import/SchoolgisUploader";
import NearbuyUploader from "./componunts/data import/listing import/NearbuyUploader";
import GoogleMapUploader from "./componunts/data import/listing import/GoogleMapUploader";
import JustdialUploader from "./componunts/data import/listing import/JustdialUploader";
import FreelistingUploader from "./componunts/data import/listing import/FreelistingUploader";
import PostOfficeUploader from "./componunts/data import/listing import/PostOfficeUploader";
import ShikshaUploader from "./componunts/data import/listing import/ShikshaUploader";
import DuplicateData from "./componunts/Source Wise data/DuplicateData";
import ShikshaData from "./componunts/Source Wise data/ShikshaData";
import IndiamartScrapper from "./componunts/scrapper/IndiamartScrapper";
import BlinkitScrapper from "./componunts/scrapper/BlinkitScrapper";
import ZeptoScrapper from "./componunts/scrapper/ZeptoScrapper";
import JiomartScrapper from "./componunts/scrapper/JiomartScrapper";
import ZomatoScrapper from "./componunts/scrapper/ZomatoScrapper";
import BigbasketScrapper from "./componunts/scrapper/BigbasketScrapper";
import JioMartData from "./componunts/product master data/JioMart";
import DmartData from "./componunts/product master data/DMart";
import ZeptoData from "./componunts/product master data/Zepto";
import BlinkIt from "./componunts/product master data/BlinkIt";
import IndiaMart from "./componunts/product master data/IndiaMart";
import AmazonUploader from "./componunts/data import/product import/AmazonUploader";
import BigBasketUploader from "./componunts/data import/product import/BigBasketUploader";
import BlinkitUploader from "./componunts/data import/product import/BlinkitUploader";
import DMartUploader from "./componunts/data import/product import/DMartuploader";
import FlipkartUploader from "./componunts/data import/product import/FlipkartUploader";
import IndiaMartUploader from "./componunts/data import/product import/IndiaMartUploader";
import JioMartUploader from "./componunts/data import/product import/JioMartUploader";
import ZeptoUploader from "./componunts/data import/product import/ZeptoUploader";
import { ScraperManager } from "./layouts/Scrapper_manager";
import ZomatoUploader from "./componunts/data import/product import/ZomatoUploader";
import { SignIn } from "./pages/auth/sign-in";
import { SignUp } from "./pages/auth/sign-up";
import MasterDataDashboard from "./componunts/MasterDataDashboard";
import LocationMasterData from "./componunts/masterdata/LocationMasterData";
import MasterCategoryManager from "./componunts/masterdata/MasterCategoryManager";
import CategoryMappingDashboard from "./componunts/masterdata/CategoryMappingDashboard";

// --- HBD Reports + Data Enrichment ---
import {
  DocumentChartBarIcon,
  PresentationChartLineIcon,
  ChartPieIcon,
  TrophyIcon,
  ListBulletIcon,
  ShareIcon,
  CircleStackIcon,
  SparklesIcon,
  Squares2X2Icon,
} from "@heroicons/react/24/solid";
import ReportsOverview from "./componunts/HBD Reports/ReportsOverview";
import HbdReport from "./componunts/HBD Reports/HbdReport";
import CountReport from "./componunts/HBD Reports/CountReport";
import RankingReport from "./componunts/HBD Reports/RankingReport";
import FieldAvailability from "./componunts/HBD Reports/FieldAvailability";
import HierarchyReport from "./componunts/HBD Reports/HierarchyReport";
import DatabaseTables from "./componunts/HBD Reports/DatabaseTables";
import DetailReport from "./componunts/HBD Reports/DetailReport";
import AllProductTables from "./componunts/Data Enrichment/AllProductTables";
import CategoriesEnrichmentReport from "./componunts/Data Enrichment/CategoriesEnrichmentReport";
import ProductsEnrichmentReport from "./componunts/Data Enrichment/ProductsEnrichmentReport";
import AttributesEnrichmentReport from "./componunts/Data Enrichment/AttributesEnrichmentReport";
import EnrichmentProcess from "./componunts/Data Enrichment/EnrichmentProcess";
import RawDataSources from "./componunts/Data Enrichment/RawDataSources";
import UrlExtractionReport from "./componunts/Data Enrichment/UrlExtractionReport";
import LocationMatchingReport from "./componunts/Data Enrichment/LocationMatchingReport";
import {
  PresentationChartLineIcon as DeProcessIcon,
  ServerStackIcon as DeRawIcon,
  LinkIcon as DeUrlIcon,
  MapPinIcon as DeLocationIcon,
} from "@heroicons/react/24/solid";

// --- NEW Phase 1 Pages ---
import CommandCenter from "./pages/admin/CommandCenter";
import PipelineStatus from "./pages/reports/PipelineStatus";
import GuidedIngestionWizard from "./pages/ingest/GuidedIngestionWizard";
import ScraperScheduler from "./pages/ingest/ScraperScheduler";
import CategoryMapper from "./pages/mapping/CategoryMapper";
import AttributeStandardizer from "./pages/mapping/AttributeStandardizer";
import DiningManager from "./pages/commerce/DiningManager";
import QuickCommerceManager from "./pages/commerce/QuickCommerceManager";
import ServicesManager from "./pages/commerce/ServicesManager";
import HealthcareManager from "./pages/commerce/HealthcareManager";
import TouristSpotsManager from "./pages/leisure/TouristSpotsManager";
import ItinerariesManager from "./pages/leisure/ItinerariesManager";
import HotelsManager from "./pages/leisure/HotelsManager";
import PlayAreasManager from "./pages/leisure/PlayAreasManager";
import HangoutHubsManager from "./pages/leisure/HangoutHubsManager";
import NewsModeration from "./pages/content/NewsModeration";
import CommunityChannels from "./pages/content/CommunityChannels";

const icon = {
  className: "w-5 h-5 text-inherit",
};

/*
 * =============================================================================
 *  ROUTE ARCHITECTURE — 7-Section Enterprise Hierarchy
 * =============================================================================
 *
 *  Section 1: DASHBOARD & OVERVIEW     (Home, Command Center, Reports)
 *  Section 2: HBD ETL & PIPELINE       (Pipeline Status, HBD Reports, Data Enrichment)
 *  Section 3: GUIDED DATA INGESTION    (Bulk Upload Wizard, Scraper Scheduler, Upload Data)
 *  Section 4: CATEGORY & CATALOG MAP   (Category Mapping, Attributes, Unmatched Review, Master Data)
 *  Section 5: COMMERCE & SERVICES      (Dining, Quick Commerce, Services, Healthcare)
 *  Section 6: LEISURE & TOURISM        (Tourist Spots, Itineraries, Hotels, Play Areas, Hangout Hubs)
 *  Section 7: LOCAL NEWS & COMMUNITY   (News Moderation, Community Channels)
 *
 *  + OPERATIONS (Legacy working screens kept intact: Source Wise, Product Master, Scrapers, etc.)
 *  + Hidden routes (detail views, product/:asin, etc.)
 * =============================================================================
 */

export const routes = [
  {
    layout: "dashboard",
    pages: [
      // =====================================================================
      // SECTION 1: DASHBOARD & OVERVIEW
      // =====================================================================
      {
        icon: <HomeIcon {...icon} />,
        name: "Dashboard & Overview",
        children: [
          {
            icon: <HomeIcon {...icon} />,
            name: "Home",
            path: "/home",
            element: <Home />,
          },
          {
            icon: <ChartBarIcon {...icon} />,
            name: "Command Center",
            path: "/admin/command-center",
            element: <CommandCenter />,
          },
          {
            icon: <ChartBarIcon {...icon} />,
            name: "Master Dashboard",
            path: "/masterdata/dashboard",
            element: <MasterDataDashboard />,
          },
          {
            icon: <ChartBarIcon {...icon} />,
            name: "Aggregate Report",
            path: "/report-data",
            element: <AggregateReport />,
          },
        ],
      },

      // =====================================================================
      // SECTION 2: HBD ETL & PIPELINE REPORTS
      // =====================================================================
      {
        icon: <DocumentChartBarIcon {...icon} />,
        name: "HBD ETL & Pipeline",
        children: [
          {
            icon: <ChartBarIcon {...icon} />,
            name: "Pipeline Status",
            path: "/reports/pipeline-status",
            element: <PipelineStatus />,
          },
          {
            icon: <ChartBarIcon {...icon} />,
            name: "Listing Data Report",
            path: "/home2",
            element: <ReportDashboard />,
          },
          {
            icon: <ShoppingCartIcon {...icon} />,
            name: "Product Data Report",
            path: "/productdata-report",
            element: <ProductDataReport />,
          },
          {
            icon: <DocumentChartBarIcon {...icon} />,
            name: "HBD Reports",
            children: [
              {
                icon: <Squares2X2Icon {...icon} />,
                name: "Overview",
                path: "/hbd-reports/overview",
                element: <ReportsOverview />,
              },
              {
                icon: <PresentationChartLineIcon {...icon} />,
                name: "HBD Report",
                path: "/hbd-reports/hbd",
                element: <HbdReport />,
              },
              {
                icon: <ChartPieIcon {...icon} />,
                name: "Count Report",
                path: "/hbd-reports/count",
                element: <CountReport />,
              },
              {
                icon: <TrophyIcon {...icon} />,
                name: "Ranking Report",
                path: "/hbd-reports/ranking",
                element: <RankingReport />,
              },
              {
                icon: <TableCellsIcon {...icon} />,
                name: "Detail Report",
                path: "/hbd-reports/detail",
                element: <DetailReport />,
              },
              {
                icon: <ListBulletIcon {...icon} />,
                name: "Master Table Fields",
                path: "/hbd-reports/field-availability",
                element: <FieldAvailability />,
              },
              {
                icon: <ShareIcon {...icon} />,
                name: "Hierarchy Check",
                path: "/hbd-reports/hierarchy",
                element: <HierarchyReport />,
              },
              {
                icon: <CircleStackIcon {...icon} />,
                name: "Database Tables",
                path: "/hbd-reports/db-tables",
                element: <DatabaseTables />,
              },
              {
                icon: <SparklesIcon {...icon} />,
                name: "Data Enrichment",
                children: [
                  {
                    icon: <DeProcessIcon {...icon} />,
                    name: "Master Report",
                    path: "/hbd-reports/data-enrichment/process",
                    element: <EnrichmentProcess />,
                  },
                  {
                    icon: <DeRawIcon {...icon} />,
                    name: "Raw Data Sources",
                    path: "/hbd-reports/data-enrichment/raw-sources",
                    element: <RawDataSources />,
                  },
                  {
                    icon: <DeUrlIcon {...icon} />,
                    name: "URL Extraction",
                    path: "/hbd-reports/data-enrichment/url-extraction",
                    element: <UrlExtractionReport />,
                  },
                  {
                    icon: <DeLocationIcon {...icon} />,
                    name: "Location Matching",
                    path: "/hbd-reports/data-enrichment/location-matching",
                    element: <LocationMatchingReport />,
                  },
                  {
                    icon: <RectangleStackIcon {...icon} />,
                    name: "All Product Tables",
                    path: "/hbd-reports/data-enrichment/all-tables",
                    element: <AllProductTables />,
                  },
                  {
                    icon: <TableCellsIcon {...icon} />,
                    name: "Categories",
                    path: "/hbd-reports/data-enrichment/categories",
                    element: <CategoriesEnrichmentReport />,
                  },
                  {
                    icon: <ShoppingCartIcon {...icon} />,
                    name: "Products",
                    path: "/hbd-reports/data-enrichment/products",
                    element: <ProductsEnrichmentReport />,
                  },
                  {
                    icon: <ListBulletIcon {...icon} />,
                    name: "Attributes",
                    path: "/hbd-reports/data-enrichment/attributes",
                    element: <AttributesEnrichmentReport />,
                  },
                ],
              },
            ],
          },
        ],
      },

      // =====================================================================
      // SECTION 3: GUIDED DATA INGESTION
      // =====================================================================
      {
        icon: <ArrowUpTrayIcon {...icon} />,
        name: "Guided Data Ingestion",
        children: [
          {
            icon: <ArrowUpTrayIcon {...icon} />,
            name: "Bulk Upload Wizard",
            path: "/ingest/bulk-upload",
            element: <GuidedIngestionWizard />,
          },
          {
            icon: <ServerStackIcon {...icon} />,
            name: "Scraper Schedules",
            path: "/ingest/scraper-schedules",
            element: <ScraperScheduler />,
          },
          {
            icon: <ServerStackIcon {...icon} />,
            name: "Master Data Uploader",
            path: "/data-imports/master-data-uploader",
            element: <MasterDataUploader />,
          },
          {
            icon: <ArrowUpTrayIcon {...icon} />,
            name: "Listing Data Upload",
            children: [
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Asklaila",
                path: "/data-imports/listing-data/asklaila",
                element: <AsklailaUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "ATM",
                path: "/data-imports/listing-data/atm",
                element: <AtmUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Bank Data",
                path: "/data-imports/listing-data/bank-data",
                element: <BankDataUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "College Dunia",
                path: "/data-imports/listing-data/college-dunia",
                element: <CollegeDuniaUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Freelisting",
                path: "/data-imports/listing-data/freelisting",
                element: <FreelistingUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Google Maps",
                path: "/data-imports/listing-data/google-maps",
                element: <GoogleMapUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Google",
                path: "/data-imports/listing-data/google",
                element: <GoogleUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Hey Places",
                path: "/data-imports/listing-data/hey-places",
                element: <HeyPlacesUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Just Dial",
                path: "/data-imports/listing-data/just-dial",
                element: <JustdialUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "NearBuy",
                path: "/data-imports/listing-data/nearbuy",
                element: <NearbuyUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Pinda",
                path: "/data-imports/listing-data/pinda",
                element: <PindaUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Post Office",
                path: "/data-imports/listing-data/post-office",
                element: <PostOfficeUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Schoolgis",
                path: "/data-imports/listing-data/schoolgis",
                element: <SchoolgisUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Shiksha",
                path: "/data-imports/listing-data/shiksha",
                element: <ShikshaUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Yellow Pages",
                path: "/data-imports/listing-data/yellow-pages",
                element: <YellowPagesUploader />,
              },
            ],
          },
          {
            icon: <ArrowUpTrayIcon {...icon} />,
            name: "Product Data Upload",
            children: [
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Amazon",
                path: "/data-imports/product-data/amazon",
                element: <AmazonUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "BigBasket",
                path: "/data-imports/product-data/big-basket",
                element: <BigBasketUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Blinkit",
                path: "/data-imports/product-data/blinkit",
                element: <BlinkitUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "D-Mart",
                path: "/data-imports/product-data/d-mart",
                element: <DMartUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Flipkart",
                path: "/data-imports/product-data/flipkart",
                element: <FlipkartUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "India Mart",
                path: "/data-imports/product-data/india-mart",
                element: <IndiaMartUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "JioMart",
                path: "/data-imports/product-data/jio-mart",
                element: <JioMartUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Zepto",
                path: "/data-imports/product-data/zepto",
                element: <ZeptoUploader />,
              },
              {
                icon: <DocumentTextIcon {...icon} />,
                name: "Zomato",
                path: "/data-imports/product-data/zomato",
                element: <ZomatoUploader />,
              },
            ],
          },
          {
            icon: <DocumentTextIcon {...icon} />,
            name: "Others Data",
            path: "/data-imports/others-data",
            element: <OthersDataImport />,
          },
        ],
      },

      // =====================================================================
      // SECTION 4: CATEGORY & CATALOG MAPPING
      // =====================================================================
      {
        icon: <Squares2X2Icon {...icon} />,
        name: "Category & Catalog Mapping",
        children: [
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Category Mapper",
            path: "/mapping/categories",
            element: <CategoryMapper />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Attribute Standardizer",
            path: "/mapping/attributes",
            element: <AttributeStandardizer />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Unmatched Data Review",
            path: "/masterdata/unmatched-data-review",
            element: <UnmatchedDataReview />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Master Categories",
            path: "/masterdata/master-categories",
            element: <MasterCategoryManager />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Category Mapping (Legacy)",
            path: "/masterdata/category-mapping",
            element: <CategoryMappingDashboard />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Listing Category",
            path: "/masterdata/listing-category",
            element: <ListingCategory />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Product Category",
            path: "/masterdata/product-category",
            element: <ProductCategory />,
          },
        ],
      },

      // =====================================================================
      // SECTION 5: COMMERCE & SERVICE MANAGERS (Phase 1 — Placeholders)
      // =====================================================================
      {
        icon: <ShoppingCartIcon {...icon} />,
        name: "Commerce & Services",
        children: [
          {
            icon: <ShoppingCartIcon {...icon} />,
            name: "Dining Manager",
            path: "/commerce/dining",
            element: <DiningManager />,
          },
          {
            icon: <ShoppingCartIcon {...icon} />,
            name: "Quick Commerce",
            path: "/commerce/quick-commerce",
            element: <QuickCommerceManager />,
          },
          {
            icon: <ShoppingCartIcon {...icon} />,
            name: "Services Manager",
            path: "/commerce/services",
            element: <ServicesManager />,
          },
          {
            icon: <ShoppingCartIcon {...icon} />,
            name: "Healthcare Manager",
            path: "/commerce/healthcare",
            element: <HealthcareManager />,
          },
        ],
      },

      // =====================================================================
      // SECTION 6: LEISURE & TOURISM MANAGERS (Phase 1 — Placeholders)
      // =====================================================================
      {
        icon: <MapPinIcon {...icon} />,
        name: "Leisure & Tourism",
        children: [
          {
            icon: <MapPinIcon {...icon} />,
            name: "Tourist Spots",
            path: "/leisure/tourist-spots",
            element: <TouristSpotsManager />,
          },
          {
            icon: <MapPinIcon {...icon} />,
            name: "Itineraries",
            path: "/leisure/itineraries",
            element: <ItinerariesManager />,
          },
          {
            icon: <MapPinIcon {...icon} />,
            name: "Hotels & Stays",
            path: "/leisure/hotels",
            element: <HotelsManager />,
          },
          {
            icon: <MapPinIcon {...icon} />,
            name: "Play Areas",
            path: "/leisure/play-areas",
            element: <PlayAreasManager />,
          },
          {
            icon: <MapPinIcon {...icon} />,
            name: "Hangout Hubs",
            path: "/leisure/hangout-hubs",
            element: <HangoutHubsManager />,
          },
        ],
      },

      // =====================================================================
      // SECTION 7: LOCAL NEWS & COMMUNITY (Phase 1 — Placeholders)
      // =====================================================================
      {
        icon: <DocumentTextIcon {...icon} />,
        name: "Local News & Community",
        children: [
          {
            icon: <DocumentTextIcon {...icon} />,
            name: "News Moderation",
            path: "/content/news-moderation",
            element: <NewsModeration />,
          },
          {
            icon: <DocumentTextIcon {...icon} />,
            name: "Community Channels",
            path: "/content/community-channels",
            element: <CommunityChannels />,
          },
        ],
      },

      // =====================================================================
      // OPERATIONS — All Existing Working Screens (preserved as-is)
      // =====================================================================
      {
        icon: <TableCellsIcon {...icon} />,
        name: "Clean Master Data",
        children: [
          {
            icon: <ChartBarIcon {...icon} />,
            name: "Cleaning Dashboard",
            path: "/masterdata/cleaning-dashboard",
            element: <DataCleaningDashboard />,
          },
          {
            icon: <ChartBarIcon {...icon} />,
            name: "Tiered Dashboard",
            path: "/masterdata/dynamic-tier-dashboard",
            element: <DynamicTierDashboard />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Listing Master",
            path: "/masterdata/clean-listing-master",
            element: <CleanListingMaster />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Product Master",
            path: "/masterdata/clean-product-master",
            element: <CleanProductMaster />,
          },
        ],
      },
      {
        icon: <TableCellsIcon {...icon} />,
        name: "Master Data Registry",
        children: [
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Master Data Table",
            path: "/masterdata/master-registry",
            element: <MasterData />,
          },
          {
            icon: <MapPinIcon {...icon} />,
            name: "Location Master",
            path: "/masterdata/location-master",
            element: <LocationMasterData />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Duplicate Data",
            path: "/masterdata/duplicate-data",
            element: <DuplicateData />,
          },
        ],
      },
      {
        icon: <TableCellsIcon {...icon} />,
        name: "Source Wise Data",
        children: [
          {
            icon: <CheckCircleIcon {...icon} />,
            name: "Complete Data",
            path: "listing-master-data/complete-data",
            element: <ListingComplete />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Google Data",
            path: "listing-master-data/google-data",
            element: <GoogleData />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Google Map Data",
            path: "listing-master-data/google-map-data",
            element: <GoogleMapData />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Duplicate Data",
            path: "listing-master-data/duplicate-data",
            element: <DuplicateData />,
          },
          {
            icon: <XCircleIcon {...icon} />,
            name: "Incomplete Data",
            path: "listing-master-data/incomplete-data",
            element: <ListingIncomplate />,
          },
        ],
      },
      {
        icon: <TableCellsIcon {...icon} />,
        name: "Product Master Data",
        children: [
          {
            icon: <CheckCircleIcon {...icon} />,
            name: "Complete Data",
            path: "product-master-data/complete-data",
            element: <ProductComplete />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Amazon Data",
            path: "product-master-data/amazon-data",
            element: <AmazonData />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "BigBasket Data",
            path: "product-master-data/bigbasket-data",
            element: <BigBasketData />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "BlinkIt Data",
            path: "product-master-data/blinkit-data",
            element: <BlinkIt />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "D-Mart Data",
            path: "product-master-data/d-mart-data",
            element: <DmartData />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Flipkart Data",
            path: "product-master-data/flipkart-data",
            element: <FlipkartData />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "India Mart Data",
            path: "listing-master-data/india-mart-data",
            element: <IndiaMart />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "JioMart Data",
            path: "product-master-data/jiomart-data",
            element: <JioMartData />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Zepto Data",
            path: "product-master-data/zepto-data",
            element: <ZeptoData />,
          },
          {
            icon: <TableCellsIcon {...icon} />,
            name: "Zomato Data",
            path: "product-master-data/zomato-data",
            element: <ZomatoData />,
          },
          {
            icon: <XCircleIcon {...icon} />,
            name: "Incomplete Data",
            path: "product-master-data/incomplete-data",
            element: <ProductIncomplate />,
          },
        ],
      },
      {
        icon: <TableCellsIcon {...icon} />,
        name: "Service Master Data",
        children: [
          {
            icon: <CheckCircleIcon {...icon} />,
            name: "Complete Data",
            path: "service-master-data/complete-data",
            element: <ServiceComplate />,
          },
          {
            icon: <XCircleIcon {...icon} />,
            name: "Incomplete Data",
            path: "service-master-data/incomplete-data",
            element: <ServiceIncomplate />,
          },
        ],
      },
      {
        icon: <ServerStackIcon {...icon} />,
        name: "Scraper Manager",
        path: "/scrapper-manager",
        element: <ScraperManager />,
      },
      {
        icon: <MagnifyingGlassIcon {...icon} />,
        name: "Scrapers",
        children: [
          {
            icon: <MapPinIcon {...icon} />,
            name: "Google Map",
            path: "/scrapper/google-map",
            element: <GoogleMapScrapper />,
          },
          {
            icon: <ShoppingCartIcon {...icon} />,
            name: "D-Mart",
            path: "/scrapper/dmart",
            element: <DmartScrapper />,
          },
          {
            icon: <ShoppingCartIcon {...icon} />,
            name: "Flipkart",
            path: "/scrapper/flipkart",
            element: <FlipkartScrapper />,
          },
          {
            icon: <ShoppingCartIcon {...icon} />,
            name: "BigBasket",
            path: "/scrapper/bigbasket",
            element: <BigbasketScrapper />,
          },
          {
            icon: <ShoppingCartIcon {...icon} />,
            name: "Blinkit",
            path: "/scrapper/blinkit",
            element: <BlinkitScrapper />,
          },
          {
            icon: <ShoppingCartIcon {...icon} />,
            name: "Zepto",
            path: "/scrapper/zepto",
            element: <ZeptoScrapper />,
          },
          {
            icon: <ShoppingCartIcon {...icon} />,
            name: "Amazon",
            path: "/scrapper/amazon",
            element: <AmazonScraper />,
          },
          {
            icon: <ShoppingCartIcon {...icon} />,
            name: "India Mart",
            path: "/scrapper/indiamart",
            element: <IndiamartScrapper />,
          },
          {
            icon: <ShoppingCartIcon {...icon} />,
            name: "Jio Mart",
            path: "/scrapper/jiomart",
            element: <JiomartScrapper />,
          },
        ],
      },

      // =====================================================================
      // SEARCH & UTILITY
      // =====================================================================
      {
        icon: <MagnifyingGlassIcon {...icon} />,
        name: "Search Keyword",
        path: "/search-keyword",
        element: <SearchKeyword />,
      },
      {
        icon: <UserCircleIcon {...icon} />,
        name: "Profile",
        path: "/profile",
        element: <Profile />,
      },
      {
        icon: <TableCellsIcon {...icon} />,
        name: "Tables",
        path: "/tables",
        element: <Tables />,
      },
      {
        icon: <InformationCircleIcon {...icon} />,
        name: "Notifications",
        path: "/notifications",
        element: <Notifications />,
      },

      // =====================================================================
      // HIDDEN ROUTES (detail views, sub-pages — rendered but not in sidebar)
      // =====================================================================
      {
        path: "/listingdata-report",
        element: <MisReportTable />,
        hidden: true,
      },
      {
        path: "/productdata-report/products/:asin",
        element: <ProductDetails />,
        hidden: true,
      },
      {
        path: "/cities-report",
        element: <CitiesReports />,
        hidden: true,
      },
      {
        path: "/categories-report",
        element: <CategoriesReports />,
        hidden: true,
      },
      {
        path: "/cities-pending-report",
        element: <CitiesPendingReport />,
        hidden: true,
      },
      {
        path: "/categories-pending-report",
        element: <CategoriesPendingReport />,
        hidden: true,
      },
      {
        path: "/dashboard/unmatched_data_review",
        element: <UnmatchedDataReview />,
        hidden: true,
      },
      {
        path: "/unmatched_data_review",
        element: <UnmatchedDataReview />,
        hidden: true,
      },
      {
        path: "/unmatched-data-review",
        element: <UnmatchedDataReview />,
        hidden: true,
      },
    ],
  },
  {
    title: "auth pages",
    layout: "auth",
    pages: [
      {
        icon: <ServerStackIcon {...icon} />,
        name: "sign in",
        path: "/sign-in",
        element: <SignIn />,
      },
      {
        icon: <RectangleStackIcon {...icon} />,
        name: "sign up",
        path: "/sign-up",
        element: <SignUp />,
      },
    ],
  },
];

export default routes;
