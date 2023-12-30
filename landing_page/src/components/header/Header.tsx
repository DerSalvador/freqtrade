import React, { useState } from "react";
import "./header.scss";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faBars } from "@fortawesome/free-solid-svg-icons";

function Header() {
  // const [isNavVisible, setNavVisibility] = useState(false);
  // const [isSmallScreen, setIsSmallScreen] = useState(false);

  // useEffect(() => {
  //   const mediaQuery = window.matchMedia("(max-width: 700px)");
  //   mediaQuery.addListener(handleMediaQueryChange);
  //   handleMediaQueryChange(mediaQuery);

  //   return () => {
  //     mediaQuery.removeListener(handleMediaQueryChange);
  //   };
  // }, []);

  // // const handleMediaQueryChange = (mediaQuery) => {
  // //   if (mediaQuery.matches) {
  // //     setIsSmallScreen(true);
  // //   } else {
  // //     setIsSmallScreen(false);
  // //   }
  // // };

  // const toggleNav = () => {
  //   setNavVisibility(!isNavVisible);
  // };

  return (
    <header className="nav_style">
      <div>
        <h3 className="logo">
          trading<span className="black-color">aas</span>
        </h3>
      </div>
      <nav className="navbar">
        <ul className="nav-list">
          <li>
            <a href="#theService" className="nav-link">
              The service
            </a>
          </li>
          <li>
            <a href="#whyKubernetes" className="nav-link">
              Why Kubernetes?
            </a>
          </li>
          <li>
            <a href="#contact" className="nav-link apply-button">
              Apply via Telegram
            </a>
          </li>
        </ul>
      </nav>
      <button className="hamburger">
        <FontAwesomeIcon icon={faBars} />
      </button>
    </header>
  );
}

export default Header;
