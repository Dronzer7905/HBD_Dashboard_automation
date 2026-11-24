import PropTypes from "prop-types";
import { useState, useEffect } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import {
  XMarkIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from "@heroicons/react/24/outline";
import {
  Button,
  IconButton,
  Typography,
  Collapse,
} from "@material-tailwind/react";
import { useMaterialTailwindController, setOpenSidenav } from "../../context";

export function Sidenav({ brandImg, brandName, routes }) {
  const [controller, dispatch] = useMaterialTailwindController();
  const { sidenavColor, sidenavType, openSidenav } = controller;

  const [openDropdown, setOpenDropdown] = useState(null);      
  const [openSubDropdown, setOpenSubDropdown] = useState(null); 

  const location = useLocation();

  const sidenavTypes = {
    dark: "bg-gradient-to-br from-gray-800 to-gray-900",
    white: "bg-white shadow-sm",
    transparent: "bg-transparent",
  };

  // Logic to close sidenav ONLY on mobile/tablet
  const handleCloseSidenav = () => {
    if (window.innerWidth < 1280) { // Tailwind's 'xl' breakpoint
      setOpenSidenav(dispatch, false);
    }
  };

  const toggleDropdown = (name) => {
    setOpenDropdown((prev) => (prev === name ? null : name));
  };

  const toggleSubDropdown = (name) => {
    setOpenSubDropdown((prev) => (prev === name ? null : name));
  };

  useEffect(() => {
    const findActiveDropdown = (pages) => {
      for (const page of pages) {
        if (page.children?.length) {
          if (page.children.some((child) => location.pathname.includes(child.path))) {
            return page.name;
          }
          const nested = findActiveDropdown(page.children);
          if (nested) return page.name;
        }
      }
      return null;
    };

    routes.forEach((route) => {
      const activeName = findActiveDropdown(route.pages);
      if (activeName) setOpenDropdown(activeName);
    });
  }, [location.pathname, routes]);

  const renderMenu = (items, level = 0, layout = "", parentPath = "") => {
    return items
      .filter((item) => !item.hidden)
      .map((item) => {
      const isParent = item.children && item.children.length > 0;
      const isSecondLevel = level === 0;
      const isThirdLevel = level === 1;
      const isOpen =
        (isSecondLevel && openDropdown === item.name) ||
        (isThirdLevel && openSubDropdown === item.name);

      const toggle = (e) => {
        e.preventDefault();
        isSecondLevel ? toggleDropdown(item.name) : toggleSubDropdown(item.name);
      };

      const base = layout ? `/${layout}` : "";
      const fullPath = level === 0 ? `${base}${item.path || ""}` : `${parentPath}/${item.path || ""}`;
      const cleanPath = fullPath.replace(/\/+/g, "/");

      return (
        <li key={item.name}>
          {isParent ? (
            <>
              <Button
                onClick={toggle}
                variant="text"
                color={sidenavType === "dark" ? "white" : "blue-gray"}
                className={`flex items-center gap-4 px-4 capitalize ${level > 0 ? "ml-4" : ""}`}
                fullWidth
              >
                {item.icon}
                <Typography color="inherit" className="font-medium capitalize truncate">
                  {item.name}
                </Typography>
                <span className="ml-auto">
                  {isOpen ? <ChevronUpIcon className="w-4 h-4" /> : <ChevronDownIcon className="w-4 h-4" />}
                </span>
              </Button>
              <Collapse open={isOpen}>
                <ul className="ml-4 mt-1 flex flex-col gap-1">
                  {renderMenu(item.children, level + 1, layout, cleanPath)}
                </ul>
              </Collapse>
            </>
          ) : (
            <NavLink to={cleanPath} onClick={handleCloseSidenav}>
              {({ isActive }) => (
                <Button
                  variant={isActive ? "gradient" : "text"}
                  color={
                    isActive
                      ? sidenavColor
                      : sidenavType === "dark"
                      ? "white"
                      : "blue-gray"
                  }
                  className={`flex items-center gap-4 px-4 capitalize ${level > 0 ? "ml-4" : ""}`}
                  fullWidth
                >
                  {item.icon}
                  <Typography color="inherit" className="font-medium capitalize">
                    {item.name}
                  </Typography>
                </Button>
              )}
            </NavLink>
          )}
        </li>
      );
    });
  };

  return (
    <aside
      className={`${sidenavTypes[sidenavType]} ${
        openSidenav ? "translate-x-0" : "-translate-x-80"
      } fixed inset-y-0 left-0 z-50 my-4 ml-4 w-72 rounded-xl transition-transform duration-300 xl:translate-x-0 border border-blue-gray-100 flex flex-col`}
    >
      <div className="relative flex-shrink-0">
        <Link to="/" className="py-4 px-8 text-center block">
          <Typography
            variant="h6"
            color={sidenavType === "dark" ? "white" : "blue-gray"}
          >
            {brandName}
          </Typography>
        </Link>
        <IconButton
          variant="text"
          color={sidenavType === "dark" ? "white" : "blue-gray"}
          size="sm"
          ripple={false}
          className="absolute right-0 top-0 grid rounded-br-none rounded-tl-none xl:hidden"
          onClick={() => setOpenSidenav(dispatch, false)}
        >
          <XMarkIcon strokeWidth={2.5} className="h-5 w-5" />
        </IconButton>
      </div>

      <div className="flex-1 overflow-y-auto m-4 pr-2 no-scrollbar">
        {routes.map(({ layout, title, pages }, key) => (
          <ul key={key} className="mb-4 flex flex-col gap-1">
            {title && (
              <li className="mx-3.5 mt-4 mb-2 ">
                <Typography
                  variant="small"
                  color={sidenavType === "dark" ? "white" : "blue-gray"}
                  className="font-black uppercase opacity-75 "
                >
                  {title}
                </Typography>
              </li>
            )}
            {renderMenu(pages, 0, layout)}
          </ul>
        ))}
      </div>
    </aside>
  );
}

Sidenav.displayName = "/src/widgets/layout/sidenav.jsx";

export default Sidenav;