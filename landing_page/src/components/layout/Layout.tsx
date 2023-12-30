import React from 'react';
import './layout.scss';
import Header from '../header/Header';
import Hero from '../hero/Hero';
import Info from '../info/info';
import Contact from '../contact/Contact';
import Footer from '../footer/footer';

function Layout() {
  return (
    <div className='layout'>
      <Hero/>
      <Info/>
      <Contact/>
      <Footer/>
    </div>
  )
}

export default Layout;
