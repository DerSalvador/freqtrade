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
                Hosting personalized <a  className="a-container"  href="https://github.com/freqtrade/freqtrade#GPL-3.0-1-ov-file" target="_blank">FREQTRADE</a> Bots on Highly Available and Secured GKE 
              </li>

              <li>Pilot Phase: 1 month free of charge</li>
              <li>Elaborated SRE (Service Level Monitoring, SLAs/SLOs/SLIs, Post mortem analyses, ...)</li>
              <li>Production Issue Anticipation by using <a  className="a-container" href="https://www.cncf.io/projects/chaosmesh/" target="_blank">Chaos Engineering Concepts</a></li>
              <li>AIOps Approaches</li>
              <li>Effective ChatGPT 4 and special LLMs for Trading and Infrastructure as Code</li>
              <li>Full Software Lifecycle Management for Freqtrade And GKE
              <ul><br/>
              <li>Running latest recommended versions</li>
              <li>Installing recommended security updates</li>
              <li>Steady Extra Vulnerability Scanning</li>
              </ul>
              </li>
              <li>API Key Security Management and Consulting</li>
              <li>
                Security Configuration (YUBI/Pass Keys, Securing API
                Keys, IP Restrictions/Whitelisting/Blacklisting, Cilium Network Policies, ...)
              </li>
              <li>Automated Updated Blacklists from <a  className="a-container" href="https://remotepairlist.com" target="_blank">Remotepairlist</a></li>
              <li>
                Backtesting of recent n Strategies from <a  className="a-container" href="https://www.freqst.com/" target="_blank">Freqtrade Strategies</a> and <br/>
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
              <li>Deploying protected or free Strategies and HyperLossFunctions
              <br/> <ul><br/>
              <li><a href="https://www.copyrightlaws.com/" className="a-container" target="_blank">Intellectual properties protected by international copyright laws</a>, jurisdiction Switzerland</li>
              <li><a href="https://swissstartupassociation.ch/content/uploads/2022/03/SSA-NDA-EN.docx" className="a-container" target="_blank">International ND Agreement</a> backed by Swiss Legal Authorities</li>
              </ul>
              </li>
              <li>FreqAI configuration with Reinforcement Learning</li>
              <li>Private Access to FreqUI Frontend via Domain/IPAddress</li>
              <li>Customized Freqtrade container image (Docker) with Dependency Management (extra python libraries, etc.)</li>
              <li>Individual Configuration updates once/day (Stake Amount, Strategy, Stoploss, ...)</li>
              <li>Private Freqtrade Strategy Onboarding</li>
              <li>Cost Control Transparency</li>
              <li>Telegram Bot Control (ForceEntry, ForceExit, Stop/Start Trader, ...) through configurable Telegram Frontend</li>
              <li>Anytime cancellation and purging of all private data with no costs</li>
              <li>Basic Introduction to <a  className="a-container" href="https://github.com/freqtrade/freqtrade#GPL-3.0-1-ov-file" target="_blank">FREQTRADE</a> for Beginners</li>
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
              Be one step ahead by using professional cloud infrastructure at scale.
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
