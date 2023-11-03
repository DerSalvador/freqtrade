import { Box, Typography } from '@mui/material';
import React, { CSSProperties, useEffect } from "react";
import { href, imageStyle } from './SupportedExchanges';


const Text = (
  <>
Kubernetes (sometimes referred to as K8s) is an open-source container orchestration platform that schedules and automates the deployment, management and scaling of containerized applications (monoliths and microservices). <br/> 
The Kubernetes platform is all about optimization — automating many of the DevOps processes that were previously handled manually and simplifying the work of software developers.<br/>
<br/>
So, what’s the secret behind the platform’s success? Kubernetes services provide load balancing and simplify container management on multiple hosts. 
<br/>They make it easy for an enterprise’s apps to have greater scalability and be flexible, portable and more productive.
<br/>
In fact, Kubernetes is the fastest growing project in the history of open-source software, after Linux. 
<br/><br/>
According to a 2021 study by the Cloud Native Computing Foundation (CNCF), from 2020 to 2021,
the number of Kubernetes engineers grew by 67% to 3.9 million. That’s 31% of all backend developers, an increase of 4 percentage points in a year.
<br/>
The increasingly widespread use of Kubernetes among DevOps teams means businesses have a lower learning curve when starting with the container orchestration platform. <br/>

  </>
);

const Kubernetes = () => {
  return (
    <Box
      display=""
      justifyContent="top"
      alignItems="top"
      height="80vh"
      marginTop="6vh"
      marginLeft="10vh"
    >
      <div> 
    <img src="images/Kubernetes-Logo.wine.svg" height={100} width={100} style={imageStyle} alt="KubernetesLogo" />Kubernetes is a trademark of Cloud Native Computing Foundation (CNCF)
    </div>   
      <div style={{ textAlign: 'left', fontStyle: 'italic', fontSize: 25, alignContent: 'left', marginTop: "2vh", marginRight: "5vh" }}>
     
       
          {Text}
    
      </div>

    </Box>
  );
};

export default Kubernetes;
