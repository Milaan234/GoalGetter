
import './App.css'


import ReactMarkdown from 'react-markdown'

import { useState, useRef, useEffect } from 'react'


function Messages({messages}) {
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  return (
    <>
      
      <div id="messagesContainer">
        {messages && messages.map((message, index) => {
            return(
                <div key={index} className={message.role === "user" ? "userMessage" : "AIMessage"}><pre><ReactMarkdown>{message.content}</ReactMarkdown></pre></div>
            )
        })}
        <div ref={messagesEndRef} />
      </div>
    </>
  )
}

export default Messages
