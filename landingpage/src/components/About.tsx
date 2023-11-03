import React from 'react';
import { Box, Typography } from '@mui/material';
import { imageStyle } from './SupportedExchanges';

const Text = (
  <>
    Erklärungstext hier <br /><br />
    geht natürlich auch mit Absätzen
  </>
);


const About = () => {
  return (
    <Box
      display="flex"
      justifyContent="top"
      alignItems="top"
      height="80vh"
      marginTop="6vh"
      marginLeft="10vh"
    >
      <div style={{ textAlign: 'center'}}>
        <Typography variant="h5" align="left" color="text.secondary" component="p">
          <b>Responsible for Content </b> except for external links<br/>
          Michael Santana Santos Mellouk<br/>
          DerSalvador GmbH<br/>
          UID:CHE‑292.260.024 - CH-ID:CH17040101968 - EHRA-ID:1003646<br/>
          +41 (0) 76 803 03 27 (Whatsapp, Telegram)<br/>
          +41 (0) 44 554 72 83<br/>
          +55 (71) 98 416 2112<br/>
          Zimmergasse 7, 8008 Zürich, Schweiz<br/>
          michael.santana.mellouk@dersalvador.com<br/> 
          www.dersalvador.com<br/>
        </Typography>
      </div>
    </Box>
  );
};

export default About;