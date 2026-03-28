import { useState } from 'react'

import './App.css'

import { Form, Button } from 'react-bootstrap'


function UserQuery({setMessages, threadID}) {
  const [userMessage, setUserMessage] = useState({role: "user", content: ""})
  

  async function callAI() {
    if(!userMessage) return;

    setMessages(prev => [...prev, userMessage, {role: "AI", content: "Loading...", "message_type": "loading"}])
    setUserMessage({role: "user", content: ""})

    console.log(userMessage)

    const response = await fetch("/ask_ai", {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            user_query: userMessage.content,
            thread_id: threadID
        }),
    })

    if (!response.ok) {
        console.log("Error")
        setMessages(prev => [...prev.slice(0, -1)])
    } else {
        const data = await response.json()
        console.log(data)
        setMessages(prev => [...prev.slice(0, -1), data])
    }
  }

  return (
    <>
      
      <div className='userQuestionInput'>
        <Form onSubmit={(e) => {e.preventDefault()}}>
          <Form.Group className="mb-3">
            <Form.Label>Enter Query:</Form.Label>
            <Form.Control type='text' value={userMessage.content} onChange={(e) => {setUserMessage({role: "user", content: e.target.value})}}></Form.Control>
            <Button type='submit' onClick={callAI}>Ask AI</Button>
          </Form.Group>
          
        </Form>
      </div>
    </>
  )
}

export default UserQuery
