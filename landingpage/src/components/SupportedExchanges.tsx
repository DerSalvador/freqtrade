import React, { CSSProperties, useEffect } from "react";
import "./SupportedExchanges.css"; // Sie können die CSS-Datei nach Bedarf anpassen
import { Container, Typography } from "@mui/material";

export const imageStyle: CSSProperties = {
    marginLeft: 15,
    marginRight: 15,
  };

const SupportedExchanges = () => {
  useEffect(() => {
    const scrollContainer = document.querySelector(".scroller-container");
    const content = document.querySelector(".scroller-content");

    const scrollSpeed = 50; // Geschwindigkeit der Animation (kleinere Zahl = schneller)

    function scroll() {
      if (scrollContainer.scrollLeft < content.clientWidth) {
        scrollContainer.scrollLeft += 1;
      } else {
        scrollContainer.scrollLeft = 0;
      }
    }

    const scrollInterval = setInterval(scroll, scrollSpeed);

    return () => {
      clearInterval(scrollInterval);
    };
  }, []);

  return (<>
    <Container disableGutters maxWidth="sm" component="main" sx={{ pt: 8, pb: 6 }} style={{paddingTop:50}}>
        <Typography
          component="h1"
          variant="h2"
          align="center"
          color="text.primary"
          gutterBottom
        >
          Supported Exchanges
        </Typography>
        <Typography variant="h5" align="center" color="text.secondary" component="p">
          We support the listed exchanges, if you need more just let us know
        </Typography>
      </Container>
    <div className="scroller-container">
      <div className="scroller-content">
        {/* Fügen Sie Ihre Logos hier ein */}
        <img src="exchanges/binance.svg" height={50} width={120} style={imageStyle} alt="binance" />
        <img src="exchanges/kraken2.svg" height={50} width={120}  style={imageStyle} alt="kraken" />
        <img src="exchanges/bitfinex.svg" height={50} width={120} style={imageStyle} alt="bitfinex" />
        <img src="exchanges/coinbase.svg" height={50} width={120}  style={imageStyle} alt="coinbase" />
        <img src="exchanges/huobi.svg" height={50} width={120} style={imageStyle} alt="huobi" />
        <img src="exchanges/kraken2.svg" height={50} width={120}  style={imageStyle} alt="kraken" />
        <img src="exchanges/okex.svg" height={50} width={120}  style={imageStyle} alt="okex" />
        {/* Fügen Sie weitere Logos hinzu, wie benötigt */}
      </div>
    </div>
    </>
  );
};

export default SupportedExchanges;
