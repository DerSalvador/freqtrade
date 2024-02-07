import "./contact.scss";

import React, { useState, useRef, useEffect } from "react" ;

function Contact() {
  const mailAdress = "trading@tradingaas.ai";

  const [sendersEmail, setSendersEmail] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");

  const onEmailChange = (value: string) => {
    setSendersEmail(value);
  };
  const onMessageChange = (value: string) => {
    setMessage(value);
  };

  const onSendPress = () => {
    setLoading(true);
    const url = `https://api.telegram.org/bot6915852728:AAFjxjFTL0Br1zilYXCwZ73_JmJ2W-DW8qU/sendMessage?chat_id=1759706931&text=${sendersEmail}%0A%0A${message}`;
    fetch(url, {
      method: "POST",
      body: JSON.stringify({
        email: sendersEmail,
        message,
      }),
    })
      .then(() => {
        setSuccessMessage("Message sent successfully!");
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
        setSuccessMessage("Unable to send message at this time.");
        //Alert.alert("Sorry", "Unable to send a message this time.");
      });
  };

  // const inputReference = useRef<HTMLInputElement | null>(null);

  // useEffect(() => {
  //   if (inputReference && inputReference.current) {
  //     inputReference.current.focus();
  //   }
  // }, []);

  const isValidEmail = () => {
    const emailRegex =
      /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
    return emailRegex.test(sendersEmail.toLowerCase());
  };
  const disabled = message.length < 10 || !isValidEmail();

  return (
    <section className="contact-section" id="contact">
      <div className="contact-info">
        <span>Apply via Telegram Message:</span>
        <h4>Get in touch today</h4>
        <h3>Initial Limited Onboarding (2 per month) after evaluation and personal interview.</h3>
        <p>Responsible for Content (except for external links)</p>

        <div className="infos">
        <p>
          <a
            href="https://www.dersalvador.com/en/home-en/"
            target="_blank"
            rel="noopener noreferrer"
          >
            DerSalvador GmbH<br /> 
          </a>
          <a href={`mailto:${mailAdress}`} target="_blank">
            {mailAdress}<br /> 
          </a>
          <a href={"https://t.me/41768030327}"} target="_blank">
            +41 (0) 76 803 03 27 (Telegram)
          </a>

          {/* <a href={"https://wa.me/5571984162112"} target="_blank">
            +55 (71) 98 416 2112 (Whatsapp)<br /> 
          </a> */}
          <a
            href={
              "https://www.google.com/maps?q=Zimmergasse%207,%208008%20Zurich,%20Switzerland"
            }
            target="_blank"
          ><br/>
          Zimmergasse 7, 8008
          Zurich, Switzerland<br/>
          {/* UID:CHE‑292.260.024 - CH-ID:CH17040101968 - EHRA-ID:1003646<br/> */}
            </a>
           
          </p>
        </div>
      </div>
      <form className="contact-card">
        <div className="form-control">
          <label htmlFor="email">Email</label>
          <input
            // ref={inputReference}
            type="email"
            id="email"
            placeholder="example@email.com"
            value={sendersEmail}
            onChange={(e) => onEmailChange(e.target.value)}
          />
        </div>
        <div className="form-control">
          <label htmlFor="message">Message</label>
          <textarea
             
            id="message"
            placeholder="Please type your message here..."
            value={message}
            onChange={(e) => onMessageChange(e.target.value)}
          />
                  <p>{successMessage}</p>
        </div>
        <button type="submit" onClick={onSendPress}>
          {loading ? "Sending..." : "Apply"}
        </button>

      </form>
    </section>
  );
  
}

export default Contact;
