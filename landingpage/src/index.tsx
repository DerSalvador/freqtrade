import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import Navbar from './components/Header';
import ContentDisplay from './components/ContentDisplay/ContentDisplay';
import Content from './components/ContentDisplay/Content';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <Navbar />
<<<<<<< HEAD
    <Scroller />
    <ContactForm />
    {/* <Pricing /> */}
    {/* <Footers /> */}
    {/* <App /> */}
=======
    <ContentDisplay content={<Content/>}/>
    {/* <Pricing /> */}
>>>>>>> 1511aa6d72 (added new ContentDisplay Component)
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
//reportWebVitals();
