import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import Pricing from './components/Pricing'
import Navbar from './components/Navbar';
import Scroller from './components/Scroller';
import Footers from './components/Footers';
import ContactForm from './components/ContactForm/ContactForm';
import Kubernetes from './components/Kubernetes';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <Navbar />
    <Scroller />
    <ContactForm />
    {/* <Pricing /> */}
    {/* <Footers /> */}
    {/* <App /> */}
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
//reportWebVitals();
