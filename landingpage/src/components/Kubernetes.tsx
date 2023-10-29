import React from 'react';
import { Box, Typography } from '@mui/material';
import { imageStyle } from './Scroller';

const Text = (
  <>
    Erklärungstext hier <br /><br />
    geht natürlich auch mit Absätzen
  </>
);

const Kubernetes = () => {
  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      height="80vh"
    >
      <div style={{ textAlign: 'center' }}>
        <img src="images/Kubernetes-Logo.wine.svg" height={400} width={400} style={imageStyle} alt="KubernetesLogo" />
        <Typography variant="h5" align="center" color="text.secondary" component="p">
          {Text}
        </Typography>
      </div>
    </Box>
  );
};

export default Kubernetes;
