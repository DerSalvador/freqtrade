import React, { CSSProperties } from 'react';
import { imageStyle } from './SupportedExchanges';

const Navbar: React.FC = () => {
  const navStyle: CSSProperties = {
    height: 90,
    marginTop:-90,
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

  const nowrap: CSSProperties = {
    whiteSpace: 'nowrap'
  };

  // const navLinkStyle: CSSProperties = {
  //   listStyleType: 'none',
  //   padding: 0,
  //   margin: 0,
  //   display: 'flex',
  //   alignItems:'center',
  //   width:'100%',
  //   justifyContent:'center',
  // };

  // const linkItemStyle: CSSProperties = {
  //   marginLeft: '20px', // Add spacing between list items
  // };

  return (
    <div style={navStyle}>
      <nav style={{ display: 'flex' , width:'100%'}}>
        <div className="logo" style={logoStyle}>
          <img src="images/logo.png" alt="Logo" height={80} style={{ marginRight: '10px' }} />
          <div style={nowrap}>Trading as a Service on Kubernetes Cloud</div>
        </div>
        <img src="images/Kubernetes-Logo.wine.svg" height={80} width={80} style={imageStyle} alt="KubernetesLogo" />
        <div className="scroller-container">
      <div className="scroller-content" >
        {/* Fügen Sie Ihre Logos hier ein */}
        <img src="exchanges/binance.svg" height={50} width={120} style={imageStyle} alt="binance" />
        <img src="exchanges/kraken2.svg" height={50} width={120}  style={imageStyle} alt="kraken" />
        <img src="exchanges/bitfinex.svg" height={50} width={120} style={imageStyle} alt="bitfinex" />
        <img src="exchanges/coinbase.svg" height={50} width={120}  style={imageStyle} alt="coinbase" />
        <img src="exchanges/huobi.svg" height={50} width={120} style={imageStyle} alt="huobi" />
        <img src="exchanges/okex.svg" height={50} width={120}  style={imageStyle} alt="okex" />
        {/* Fügen Sie weitere Logos hinzu, wie benötigt */}
      </div>
    </div>        
        {/* <ul className="nav-links" style={navLinkStyle}>
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
        </ul> */}
      </nav>
    </div>
  );
};

export default Navbar;
