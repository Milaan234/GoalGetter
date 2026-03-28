import { useEffect, useState } from 'react'
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css'

import Chatbot from './Chatbot'

import {Button, Row, Col, Container, Form} from 'react-bootstrap'
import Login from './Login';
import Settings from './Settings'



function App() {

  const [loggedIn, setLoggedIn] = useState(false)
  const [user, setUser] = useState(null)

  const [allChats, setAllChats] = useState([])

  const [messages, setMessages] = useState([])
  const [chatName, setChatName] = useState("")
  const [currThreadID, setCurrThreadID] = useState("")

  const [newChatName, setNewChatName] = useState("")

  const [showSettings, setShowSettings] = useState("")

  useEffect(() => {
    // get from flask backend if user is logged in
    
    async function getLoginData() {
      const response = await fetch('/getLoginData')
      if(response.ok) {
        const cleanedData = await response.json()
        setLoggedIn(cleanedData.loggedIn)
        setUser(cleanedData)
      } else {
        console.log("Error fetching login data")
        setLoggedIn(false)
        setUser(null)
      }
    }

    getLoginData()
  }, [])

  useEffect(() => {
    if(loggedIn) {
      getChats()
    }
  }, [loggedIn])

  async function getChats() {
    if (loggedIn) {
      const response = await fetch('/get_all_chats')
      if(response.ok) {
        const cleanedData = await response.json()
        const chats = cleanedData.message
        console.log("All chats data:", chats)
        setAllChats(chats)

        if(chats.length > 0) {
          fetchChat(chats[0].thread_id, chats[0].chat_name)
        }
      } else {
        console.log("Error fetching chats data")
        setAllChats([])
      }
    }
  }

  

  async function createChat() {
    if(!newChatName) return;
    const chatName = newChatName
    const response = await fetch('/create_chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        chat_name: chatName
      }),
    });
    if(response.ok) {
      const cleanedData = await response.json();
      const new_thread_id = cleanedData.message
      console.log("New Thread", new_thread_id)
      setNewChatName("")
      getChats()
      fetchChat(new_thread_id, chatName)
      setCurrThreadID(new_thread_id)
    } else {
      console.log("Error creating new chat")
      alert("Error creating new chat!")
    }
  }

  async function fetchChat(thread_id, chat_name) {

    const response = await fetch('/get_chat_messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        thread_id: thread_id
      }),
    });

    if(response.ok) {
      const cleanedData = await response.json()
      console.log("Chat messages for thread " + thread_id + ": ", cleanedData)
      setMessages(cleanedData.message)
      setChatName(chat_name)
      setCurrThreadID(thread_id)
    } else {
      console.log("Error retrieving chat messages")
    }
  }

  return (
    <>
      {!loggedIn && <Login />}

      {loggedIn &&
        <div id="appWrapper">
    
          <div className="header-container">
            <h1>Hello {user?.user_name},</h1>
            <h2>What will we achieve today?</h2>
            <Button onClick={()=>{setShowSettings(!showSettings)}} variant='outline-primary' size="sm">Settings</Button>
            <Settings showSettings={showSettings} setShowSettings={setShowSettings} />
            <Button onClick={()=>{window.location.href = '/logout';}} variant='outline-danger' size="sm">Logout</Button>
          </div>
    
          <Container>
            <Row>
              <Col id="chats" xs={12} md={3} lg={3} >
                <Form onSubmit={(e) => {e.preventDefault(); createChat()}}>
                  <Form.Control type="text" value={newChatName} onChange={(e)=>{setNewChatName(e.target.value)}} size="sm" />
                  <Button type="submit">+</Button>
                </Form>
                {allChats.length > 0
                ?
                  allChats.map((chat, index) => {
                    return (
                      <Button key={index} onClick={()=>{fetchChat(chat.thread_id, chat.chat_name)}} className={`ChatOption ${chat.thread_id === currThreadID ? "active" : ""}`}>{chat.chat_name}</Button>
                    )
                  })
                :
                  <h4>No Chats Yet</h4>
                }
              </Col>
              
              <Col id="previewCol" xs={12} md={9} lg={9} >
                {chatName
                ? 
                  <Chatbot messages={messages} setMessages={setMessages} chatName={chatName} threadID={currThreadID} />
                :
                  <h2>Create a Chat to get started</h2>
                }
                
              </Col>
            </Row>
          </Container>

          
        </div>

        
        
      }
    </>
  )
}

export default App
