import React from 'react';
import { Box, Typography } from '@mui/material';


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
      justifyContent="top"
      alignItems="top"
      height="80vh"
      marginTop="6vh"
      marginLeft="10vh"
    >
      <div style={{ textAlign: 'center' }}>
       
        <Typography variant="h5" align="center" color="text.secondary" component="p">
          {Text}
        </Typography>
      </div>
    </Box>
  );
};

export default Kubernetes;
