
import React, { CSSProperties, useEffect } from "react";
import { Box, Typography } from '@mui/material';
import { href, imageStyle } from './SupportedExchanges';



const Text = (
  <>

    <h3> Fully Automated <a href="https://www.freqtrade.io/en/stable/" style={href} target="_blank">NoOPs Freqtrading</a> in the Cloud</h3>
    <div> 
    <img src="images/Kubernetes-Logo.wine.svg" height={20} width={20} style={imageStyle} alt="KubernetesLogo" />Hosting Personal Trading Bots on High Available Kubernetes Cluster in the Cloud (One Namespace per Bot)
    </div>   
    <br/> 
    <div> 
    <img src="images/Kubernetes-Logo.wine.svg" height={20} width={20} style={imageStyle} alt="KubernetesLogo" />Security Configuration Consulting (YUBI/Pass Keys, Securing API Keys, IP Restrictions, Whitelisting, Blacklisting, ...)
    </div>  
    <br/> 
    <div> 
    <img src="images/Kubernetes-Logo.wine.svg" height={20} width={20} style={imageStyle} alt="KubernetesLogo" />Updated Blacklists from remotepairlist.com
    </div>  
    <br/> 
    <div> 
    <img src="images/Kubernetes-Logo.wine.svg" height={20} width={20} style={imageStyle} alt="KubernetesLogo" />Daily Backtesting for about 40 updated Strategies (<a href="https://www.freqst.com/" target="_blank">Freqtrade Strategies</a>)
    </div>   
    <br/>
    <div>
    <img src="images/Kubernetes-Logo.wine.svg" height={20} width={20} style={imageStyle} alt="KubernetesLogo" />Hyperopting Best Strategy (profit_total_abs, ...) on a daily basis
    </div>   
    <br/> 
    <div> 
    <img src="images/Kubernetes-Logo.wine.svg" height={20} width={20} style={imageStyle} alt="KubernetesLogo" />Deploying own Strategies/HyperLossFunctions
    </div>   
    <br/>
    <div> 
    <img src="images/Kubernetes-Logo.wine.svg" height={20} width={20} style={imageStyle} alt="KubernetesLogo" />Deploying Best Strategy including Hyperopt Parameter File to Personal Bots 
    </div>   
    <br/>
    <div>
    <img src="images/Kubernetes-Logo.wine.svg" height={20} width={20} style={imageStyle} alt="KubernetesLogo" />Personal Managing, Monitoring and Alerting 24/7 via Telegram 
    </div>   
    <br/>
    <div>
    <img src="images/Kubernetes-Logo.wine.svg" height={20} width={20} style={imageStyle} alt="KubernetesLogo" />Limited Onboarding (2 per month) after evaluation and personal interview  
    </div>   
 
  </>
);


const WhatWeOffer = () => {
  return (
    <Box
      display="flex"
      justifyContent="top"
      alignItems="top"
      height="80vh"
      marginTop="2.5vh"
      marginLeft="10vh"
    >
      <div style={{ textAlign: 'left'}}>
        <Typography variant="h5" align="left" color="text.secondary" component="p">
          {Text}
        </Typography>
      </div>
    </Box>
  );
};

export default WhatWeOffer;