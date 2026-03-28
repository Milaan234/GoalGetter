
import { useState } from 'react'
import './App.css'

import { Modal, Button, Form, Alert } from 'react-bootstrap'


function Settings({showSettings, setShowSettings}) {

    const [gemini_api_key, set_gemini_api_key] = useState("")
    const [showError, setShowError] = useState(false)

  
  async function updateSettings() {
    const new_gemini_api_key = gemini_api_key;
    const response = await fetch('/updateSettings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            gemini_api_key: new_gemini_api_key
        })
    })

    if(response.ok) {
        const cleanedResponse = await response.json()
        if(cleanedResponse.success) {
            set_gemini_api_key("")
            setShowError(false)
            setShowSettings(false)
        } else {
            setShowError(true)
        }
    } else {
        setShowError(true)
    }
  }

  return (
    <>
      
      <Modal show={showSettings} onHide={() => setShowSettings(false)} centered>
        <Modal.Header closeButton>
            <Modal.Title>Settings</Modal.Title>
        </Modal.Header>
        
        <Modal.Body>
            <Form onSubmit={(e) => {e.preventDefault()}}>
                <Form.Group>
                    <Form.Label>Gemini API Key (Note, you will not see your key if you entered it before for security reasons)</Form.Label>
                    <Form.Control type="password" value={gemini_api_key} onChange={(e) => {set_gemini_api_key(e.target.value)}}></Form.Control>
                </Form.Group>
            </Form>
            {showError && <Alert variant="danger">Error updating settings</Alert>}
        </Modal.Body>
        
        <Modal.Footer>
            <Button variant="secondary" onClick={() => setShowSettings(false)}>
            Cancel
            </Button>
            <Button variant="primary" onClick={updateSettings}>
            Update
            </Button>
        </Modal.Footer>
      </Modal>
    </>
  )
}

export default Settings
