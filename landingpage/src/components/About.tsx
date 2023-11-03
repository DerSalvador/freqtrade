import React from 'react';
import { Box, Typography } from '@mui/material';
import { imageStyle } from './SupportedExchanges';

const About = () => {
  return (
    <Box
      display="flow"
      justifyContent="top"
      alignItems="top"
      height="80vh"
      marginTop="6vh"
      marginLeft="5vh"
    >
      <div>
       <b>Responsible for Content </b> (except for external links)<br/>
       </div>
      <div style={{ textAlign: 'left', fontStyle: 'italic', fontSize: 20, alignContent: 'left', marginTop: "5vh"}}>
          DerSalvador GmbH<br/>
          <div style={{ textAlign: 'left', fontStyle: 'italic', fontSize: 12, alignContent: 'left', marginTop: "2vh"}}> <a href="mailto:contact@dersalvador.com" target="_blank">contact@dersalvador.com</a> 
          <a href="https://www.dersalvador.com" target="_blank" > - Website</a><br/></div>
          <div style={{ textAlign: 'left', fontStyle: 'italic', fontSize: 15, alignContent: 'left', marginTop: "2vh"}}> 
          Michael Santana Santos Mellouk<br/>
          +41 (0) 76 803 03 27 (Telegram)<br/>
          +41 (0) 44 554 72 83<br/>
          +55 (71) 98 416 2112<br/>
          Zimmergasse 7, 8008 Zurich, Switzerland<br/>

          <div style={{ textAlign: 'left', fontStyle: 'italic', fontSize: 12, alignContent: 'left', marginTop: "2vh"}}> UID:CHE‑292.260.024 - CH-ID:CH17040101968 - EHRA-ID:1003646<br/></div>
          </div>
      </div>
    </Box>
  );
};

export default About;