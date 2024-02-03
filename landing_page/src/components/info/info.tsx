import "./info.scss";

import React from "react";
import binance from "../../assets/exchanges/binance.svg";
import bitfinex from "../../assets/exchanges/bitfinex.svg";
import coinbase from "../../assets/exchanges/coinbase.svg";
import freqtrade from "../../assets/freqtrade.png";
import huobi from "../../assets/exchanges/huobi.svg";
import kraken from "../../assets/exchanges/kraken.svg";
import okx from "../../assets/exchanges/okx.svg";

function info() {
  const logos = [binance, bitfinex, coinbase, huobi, kraken, okx];
  const platforms = ["https://binance.com","https://bitfinex.com","https://coinbase.com","https://huobi.com","https://kraken.com","https://okx.com"]

  return (
    <>
      <section className="exchanges-section">
        <h6>Supported Exchanges</h6>
        <div className="exchanges-container">
          {logos.map((logo, index) => (
            <a href={platforms[index]} target="_blank"><img key={index} src={logo} alt={`Logo ${index + 1}`} /></a> 
          ))}
        </div>
      </section>
      <section className="info-container" id="theService">
        <h3 className="section-title">The Service</h3>

        <div className="card-container">
          <div className="offer-card">
            <h4>What we offer</h4>
            <ul>
              <li>
                Hosting personalized Freqtrading Bots on High Available and Secured Kubernetes
                Cluster in the Cloud 
              </li>
              <li>
                Limited Onboarding (2 per month) after evaluation and personal
                interview
              </li>
              <li>Pilot Phase: 1 month free of charge</li>
              <li>Elaborated SRE (Service Level Monitoring, SLAs/SLOs/SLIs, Post mortem analyses, ...)</li>
              <li>API Key Security Management and Consulting</li>
              <li>
                Security Configuration Consulting (YUBI/Pass Keys, Securing API
                Keys, IP Restrictions, Whitelisting, Blacklisting, Cilium Network Policies, ...)
              </li>
              <li>Automated Updated Blacklists from remotepairlist.com</li>
              <li>
                Backtesting of recent 10 Strategies from <a  className="a-container" href="https://www.freqst.com/" target="_blank">Freqtrade Strategies</a> and <br/>
                <a  className="a-container" href="https://strat.ninja/strategies.php" target="_blank">Freqtrade Strategy Ninja</a> as well as strategies from other sources
              </li>
              <li>
                Hyperopting Best Strategy (profit_total_abs, ...) on a daily
                basis
              </li>
              <li>
                Best Strategy deployment including Hyperopt Parameter File to
                Personal Bots
              </li>
              <li>Deploying customized or free Strategies and HyperLossFunctions
              <br/> <ul><br/>
              <li><a href="https://www.copyrightlaws.com/" className="a-container">Intellectual properties protected by international copyright laws</a>, jurisdiction Switzerland</li>
              <li>International ND Agreement backed by Swiss officials</li>
              </ul>
              </li>
              <li>FreqAI configuration with Reinforcement Learning section</li>
              <li>Private access to FreqUI frontend via domain/ip</li>
              <li>Customized freqtrade container image (Docker) with Dependency Management (extra python libraries, etc.)</li>
              <li>Individual Configuration updates once per day (Stake amount, Strategy, Stoploss, ...)</li>
              <li>Private freqtrade strategy onboarding</li>
              <li>Cost Control Transparency</li>
              <li>Telegram Bot Control (ForceBuy, ForceSell, Stop/Start trading, ...) through configurable Telegram Frontend</li>
              <li>Anytime cancellation and purging of all private data with no costs</li>
            </ul>
            <a href="#contact">Get started</a>
          </div>
          <div className="planning-card">
            <h4>Features in planning</h4>
            <p>
              Be one step ahead by using high available operating improvements
            </p>
            <ul>
              <li>
                Changing Configuration Parameters like Strategy/Stake Amount via
                Telegram Command during Runtime without Redeployment
              </li>
              <li>Consulting recommendation platforms like TA API for crypto pair specific trading directions (short, long)</li>
              <li>
                more to come...
              </li>
            </ul>
          </div>
        </div>
      </section>
      <section className="kubernetes-container" id="whyKubernetes">
        <h3 className="section-title">Why Kubernetes</h3>
        <div >
        <p className="p-container">Freqtrade Bots running for different tenants and trading APIs</p>
          <img className="image-container" src={freqtrade} alt="GKE Image" />
        </div>
        <p>
          Kubernetes (sometimes referred to as K8s) is an open-source container
          orchestration platform that schedules and automates the deployment,
          management and scaling of containerized applications (monoliths and
          microservices). The Kubernetes platform is all about optimization —
          automating many of the DevOps processes that were previously handled
          manually and simplifying the work of software developers.
        </p>
        <p>
          So, what’s the secret behind the platform’s success? Kubernetes
          services provide load balancing and simplify container management on
          multiple hosts. They make it easy for an enterprise’s apps to have
          greater scalability and be flexible, portable and more productive. In
          fact, Kubernetes is the fastest growing project in the history of
          open-source software, after Linux.
        </p>
        <p>
          According to a 2021 study by the Cloud Native Computing Foundation
          (CNCF), from 2020 to 2021, the number of Kubernetes engineers grew by
          67% to 3.9 million. That’s 31% of all backend developers, an increase
          of 4 percentage points in a year. The increasingly widespread use of
          Kubernetes among DevOps teams means businesses have a lower learning
          curve when starting with the container orchestration platform.
        </p>
      </section>
    </>
  );
}

export default info;
