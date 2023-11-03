import React, { useState } from 'react';
import { Container, TextField, Button } from '@mui/material';
import { Box, Typography } from '@mui/material';

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
    const url =`https://api.telegram.org/bot6915852728:AAFjxjFTL0Br1zilYXCwZ73_JmJ2W-DW8qU/sendMessage?chat_id=1759706931&text=${sendersEmail}%0A%0A${message}`;
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
    <Box
      display="flow"
      justifyContent="top"
      alignItems="top"
      height="80vh"
      marginTop="6vh"
      marginLeft="5vh"
      marginRight="60vh"
    >
      <div style={{ textAlign: 'left', fontStyle: 'italic', fontSize: 20, alignContent: 'left', marginTop: "5vh"}}>Apply via Telegram Message:</div>
      <TextField
        value={sendersEmail}
        type="email"
        variant="outlined"
        fullWidth
        label="Your email"
        onChange={(e) => onEmailChange(e.target.value)}
        placeholder="Your email"
        style={{ marginBottom: '25px' ,marginTop:50,backgroundColor: 'white'}}
      />
      <TextField
        value={message}
        variant="outlined"
        fullWidth
        label="Your message  (at least 10 characters)"
        onChange={(e) => onMessageChange(e.target.value)}
        multiline
        rows={4}
        placeholder="Your message..."
        style={{ marginBottom: '25px'  ,backgroundColor: 'white'}}
      />
      <Button
        variant="contained"
        color="primary"
        onClick={onSendPress}
        disabled={disabled}
        style={{ width: '50%', marginTop: '20px',margin:'auto'}}
      >
        {loading ? 'Sending...' : 'Send'}
      </Button>
    </Box>
  );
};

export default ContactForm;
