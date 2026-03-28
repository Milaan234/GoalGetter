import { useState, useRef } from 'react'

import './App.css'


import UserQuery from './UserQuery'
import Messages from './Messages'


function Chatbot({messages, setMessages, chatName, threadID}) {

  
  

  return (
    <>
      
      <div id="chatbotContainer">
        <h2>{chatName}</h2>
        <Messages messages={messages} />
        <UserQuery threadID={threadID} setMessages={setMessages} />
      </div>
    </>
  )
}

export default Chatbot
