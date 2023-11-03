
import React, { CSSProperties, useEffect } from "react";
import { Box, Typography } from '@mui/material';
import { href, imageStyle } from './SupportedExchanges';



const Text = (
  <>

   <h3>Planned Operating Features</h3>
   <div style={{ textAlign: 'left', fontStyle: 'italic', fontSize: 12, alignContent: 'left', marginRight: "5vh", marginBottom: "3vh" }}>Be one step ahead by using high available operating improvements</div>
   <div>
    <img src="images/Kubernetes-Logo.wine.svg" height={20} width={20} style={imageStyle} alt="KubernetesLogo" />Changing Config Parameters like Strategy/Stake Amount via Telegram Command during Runtime without Redeployment  
    </div>  
    <br/>
    <div>
    <img src="images/Kubernetes-Logo.wine.svg" height={20} width={20} style={imageStyle} alt="KubernetesLogo" />Please feel free to suggest more improvements for evaluation...
    </div>  
  </>
);


const NewFeatures = () => {
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

export default NewFeatures;