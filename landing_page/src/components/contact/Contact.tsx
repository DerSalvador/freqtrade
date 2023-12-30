import React, { useState } from "react";
import "./contact.scss";

function Contact() {
  const mailAdress = "contact@dersalvador.com";

  const [sendersEmail, setSendersEmail] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

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
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
        //Alert.alert("Sorry", "Unable to send a message this time.");
      });
  };
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
        <p>Responsible for Content (except for external links)</p>

        <div className="infos">
          <a
            href="https://www.dersalvador.com"
            target="_blank"
            rel="noopener noreferrer"
          >
            dersalvador.com - Website
          </a>
          <a href={`mailto:${mailAdress}`}>
            contact@dersalvador.com
          </a>
          <a href={"https://t.me/41768030327}"}>
            +41 (0) 76 803 03 27 (Telegram)
          </a>
          <a href={"https://wa.me/410445547283"}>+41 (0) 44 554 72 83</a>
          <a href={"https://wa.me/5571984162112"}>+55 (71) 98 416 2112</a>
          <a
            href={
              "https://www.google.com/maps?q=Zimmergasse%207,%208008%20Zurich,%20Switzerland"
            }
          >
            Zimmergasse 7, 8008 <br />
            Zurich, Switzerland
          </a>
          <p>
            UID:CHE‑292.260.024 <br /> CH-ID:CH17040101968 <br />{" "}
            EHRA-ID:1003646
          </p>
        </div>
      </div>
      <form className="contact-card">
        <div className="form-control">
          <label htmlFor="email">Email</label>
          <input type="email" id="email" placeholder="example@email.com" value={sendersEmail} onChange={(e) => onEmailChange(e.target.value)}/>
        </div>
        <div className="form-control">
          <label htmlFor="message">Message</label>
          <textarea
            id="message"
            placeholder="Please type your message here..."
            value={message}
            onChange={(e) => onMessageChange(e.target.value)}
          />
        </div>
        <button type="submit" onClick={onSendPress}>{loading ? 'Sending...' : 'Apply'}</button>
      </form>
    </section>
  );
}

export default Contact;
