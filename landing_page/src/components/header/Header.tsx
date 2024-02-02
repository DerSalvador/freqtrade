import "./header.scss";

import React, { useState } from "react";

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faBars } from "@fortawesome/free-solid-svg-icons";

function Header() {
  const [showMenu, setShowMenu] = useState(false);

  const toggleMenu = () => {
    setShowMenu(!showMenu);
  };
  const rootUrl = window.location.origin;

  return (
    <header className="nav_style">
      <div>
        <h3 className="logo">
          <a href={rootUrl}>trading<span className="black-color">aas</span></a>
        </h3>
      </div>
      <nav className="navbar">
        <ul className="nav-list">
        <li>
            <a href="#termsandconditions" className="nav-link">
              Terms and Conditions
            </a>
          </li>
          <li>
            <a href="#theService" className="nav-link">
              The Service
            </a>
          </li>
          <li>
            <a href="#whyKubernetes" className="nav-link">
              Why Kubernetes
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
      {showMenu && <div>
        
        </div>}
    </header>
  );
}

export default Header;
