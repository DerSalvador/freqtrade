import React from 'react';
import { Box, Typography } from '@mui/material';
import { imageStyle } from './SupportedExchanges';

const Text = (
  <>
    <h2>Running Trading Bots</h2>
    <li>Hosting you personalized and customized bot based on the Open Source Solution Freqtrade on Kubernetes Cluster (Digital Ocean)</li>
    <li></li>
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