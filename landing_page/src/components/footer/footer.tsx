import React from 'react';


import './footer.scss';
const version = process.env.VERSION || '1.1'; // Get the version from the environment variable or use a default value

function footer() {
  console.log(`The current version is ${process.env.VERSION}`);

  return (
    <div className='footer-container'>
      <p>Copyright © Trading
      as a Service 2024.</p>
      <p>All Rights Reserved</p> 
      <p>Version: {version}</p>
    </div>
  )
}

export default footer;


