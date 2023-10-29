import React, { CSSProperties } from 'react';

const Navbar: React.FC = () => {
  const navStyle: CSSProperties = {
    height: 90,
    position: 'fixed',
    background: 'linear-gradient(to right, blue, blueviolet)',
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    padding: '0 20px',
    color: 'white',
    fontSize: '1.5rem',
    zIndex:15
  };

  const logoStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
  };

  const navLinkStyle: CSSProperties = {
    listStyleType: 'none',
    padding: 0,
    margin: 0,
    display: 'flex',
    alignItems:'center',
    width:'100%',
    justifyContent:'center',
  };

  const linkItemStyle: CSSProperties = {
    marginLeft: '20px', // Add spacing between list items
  };

  return (
    <div style={navStyle}>
      <nav style={{ display: 'flex' , width:'100%'}}>
        <div className="logo" style={logoStyle}>
          <img src="images/logo.png" alt="Logo" height={80} style={{ marginRight: '10px' }} />
          <span>freqtrade-boys</span>
        </div>
        <ul className="nav-links" style={navLinkStyle}>
          <li style={linkItemStyle}>
            <a href="#what-we-do" style={{ color: 'white' }}>
              What We Do
            </a>
          </li>
          <li style={linkItemStyle}>
            <a href="#pricing" style={{ color: 'white' }}>
              Pricing
            </a>
          </li>
        </ul>
      </nav>
    </div>
  );
};

export default Navbar;
