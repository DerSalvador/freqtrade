import React, { useState } from 'react';
import { Container, TextField, Button } from '@mui/material';


const ContactForm: React.FC<{}> = () => {

  const [ sendersEmail, setSendersEmail ] = useState("");
  const [ message, setMessage ] = useState("");
  const [ loading, setLoading ] = useState(false);


  const onEmailChange = (value) => {
    setSendersEmail(value);
  };
  const onMessageChange = (value) => {
    setMessage(value);
  };
  const onSendPress = () => {
    setLoading(true);
    const url =`https://api.telegram.org/bot6682467333:AAGZb8iXECztbpzamiIpBWaN630AJ-E_Gi4/sendMessage?chat_id=477936067&text=${sendersEmail}%0A%0A${message}`;
    fetch(url, {
      method: "POST",
      body: JSON.stringify({
        email: sendersEmail,
        message
      })
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
    const emailRegex = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
    return emailRegex.test(sendersEmail.toLowerCase());
  };
  const disabled = message.length < 10 || !isValidEmail();
  return (
    <Container>
      <TextField
        value={sendersEmail}
        type="email"
        variant="outlined"
        fullWidth
        label="Your email"
        onChange={(e) => onEmailChange(e.target.value)}
        placeholder="Your email"
      />
      <TextField
        value={message}
        variant="outlined"
        fullWidth
        label="Your message"
        onChange={(e) => onMessageChange(e.target.value)}
        multiline
        rows={4}
        placeholder="Your message..."
      />
      <Button
        variant="contained"
        color="primary"
        onClick={onSendPress}
        disabled={disabled}
      >
        {loading ? 'Sending...' : 'Send'}
      </Button>
    </Container>
  );
};

export default ContactForm;
