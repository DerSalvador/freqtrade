import React from "react";
import "./info.scss";
import binance from "../../assets/exchanges/binance.svg";
import bitfinex from "../../assets/exchanges/bitfinex.svg";
import coinbase from "../../assets/exchanges/coinbase.svg";
import huobi from "../../assets/exchanges/huobi.svg";
import kraken from "../../assets/exchanges/kraken.svg";
import okx from "../../assets/exchanges/okx.svg";

function info() {
  const logos = [binance, bitfinex, coinbase, huobi, kraken, okx];

  return (
    <>
      <section className="exchanges-section">
        <h6>Supported Exchanges</h6>
        <div className="exchanges-container">
          {logos.map((logo, index) => (
            <img key={index} src={logo} alt={`Logo ${index + 1}`} />
          ))}
        </div>
      </section>
      <section className="info-container" id="theService">
        <h3 className="section-title">The service</h3>
        <div className="card-container">
          <div className="offer-card">
            <h4>What we offer</h4>
            <ul>
              <li>
                Hosting Personal Trading Bots on High Available Kubernetes
                Cluster in the Cloud (One Namespace per Bot)
              </li>
              <li>
                Security Configuration Consulting (YUBI/Pass Keys, Securing API
                Keys, IP Restrictions, Whitelisting, Blacklisting, ...)
              </li>
              <li>Updated Blacklists from remotepairlist.com</li>
              <li>
                Daily Backtesting for about 40 updated Strategies (Freqtrade
                Strategies)
              </li>
              <li>
                Hyperopting Best Strategy (profit_total_abs, ...) on a daily
                basis
              </li>
              <li>Deploying own Strategies/HyperLossFunctions</li>
              <li>
                Deploying Best Strategy including Hyperopt Parameter File to
                Personal Bots
              </li>
              <li>
                Deploying Best Strategy including Hyperopt Parameter File to
                Personal Bots
              </li>
              <li>
                Limited Onboarding (2 per month) after evaluation and personal
                interview
              </li>
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
                Changing Config Parameters like Strategy/Stake Amount via
                Telegram Command during Runtime without Redeployment
              </li>
              <li>
                Please feel free to suggest more improvements for evaluation...
              </li>
            </ul>
          </div>
        </div>
      </section>
      <section className="kubernetes-container" id="whyKubernetes">
        <h3 className="section-title">Why Kubernetes?</h3>
        <p>
          Kubernetes (sometimes referred to as K8s) is an open-source container
          orchestration platform that schedules and automates the deployment,
          management and scaling of containerized applications (monoliths and
          microservices).The Kubernetes platform is all about optimization —
          automating many of the DevOps processes that were previously handled
          manually and simplifying the work of software developers.
        </p>
        <p>
          So, what’s the secret behind the platform’s success? Kubernetes
          services provide load balancing and simplify container management on
          multiple hosts.They make it easy for an enterprise’s apps to have
          greater scalability and be flexible, portable and more productive.In
          fact, Kubernetes is the fastest growing project in the history of
          open-source software, after Linux
        </p>
        <p>
          .According to a 2021 study by the Cloud Native Computing Foundation
          (CNCF), from 2020 to 2021, the number of Kubernetes engineers grew by
          67% to 3.9 million. That’s 31% of all backend developers, an increase
          of 4 percentage points in a year.The increasingly widespread use of
          Kubernetes among DevOps teams means businesses have a lower learning
          curve when starting with the container orchestration platform.
        </p>
      </section>
    </>
  );
}

export default info;
