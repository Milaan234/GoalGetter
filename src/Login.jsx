import { useState } from 'react'
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css'

import {Button, Card, Container, Row, Col, Navbar} from 'react-bootstrap'

import gmailIcon from './assets/gmail.png';
import calendarIcon from './assets/calendar.png';
import tasksIcon from './assets/tasks.png';


function Login() {

  async function login() {
    window.location.href = '/login';
  }

  return (
    <div className="landing-page">
      {/* Navigation Bar */}
      <Navbar className="landing-navbar" expand="lg">
        <Container>
          <Navbar.Brand className="brand-logo">Goal Getter</Navbar.Brand>
          <Navbar.Toggle aria-controls="basic-navbar-nav" />
          <Navbar.Collapse className="justify-content-end">
            <Button variant="outline-primary" className="nav-login-btn" onClick={login}>Sign In</Button>
          </Navbar.Collapse>
        </Container>
      </Navbar>

      {/* Hero Section */}
      <Container className="hero-section text-center">
        <h1 className="hero-title">Turn Your Ambitions Into Achievements</h1>
        <p className="hero-subtitle">
          An AI-powered Goal Planning Assistant that seamlessly integrates with your Google Workspace and gives actionable insights to keep you on track.
        </p>
        <Button size="lg" className="cta-button" onClick={login}>Get Started</Button>
      </Container>

      {/* Features Grid */}
      <Container className="features-section">
        <Row className="g-4">
          <Col xs={12} md={4}>
            <Card className="feature-card h-100 text-center">
              <Card.Body>
                <div className="feature-icon"><img src={gmailIcon} alt="Gmail Integration" /></div>
                <Card.Title>Gmail</Card.Title>
                <Card.Text>Draft and send emails automatically to keep your plans and roadmap in the loop and projects moving.</Card.Text>
              </Card.Body>
            </Card>
          </Col>
          <Col xs={12} md={4}>
            <Card className="feature-card h-100 text-center">
              <Card.Body>
                <div className="feature-icon"><img src={calendarIcon} alt="Google Calendar Integration" /></div>
                <Card.Title>Google Calendar</Card.Title>
                <Card.Text>Schedule blocks of time for deep work, add deadlines, and review your upcoming events.</Card.Text>
              </Card.Body>
            </Card>
          </Col>
          <Col xs={12} md={4}>
            <Card className="feature-card h-100 text-center">
              <Card.Body>
                <div className="feature-icon"><img src={tasksIcon} alt="Google Tasks Integration" style={{ width: '25%', height: 'auto' }} /></div>
                <Card.Title>Google Tasks</Card.Title>
                <Card.Text>Break down massive goals into actionable, bite-sized daily tasks that sync instantly.</Card.Text>
              </Card.Body>
            </Card>
          </Col>
        </Row>
      </Container>

      {/* Example Chat Interactions with AI */}
      <Container className="examples-section text-center">
        <h2 className="mb-4 fw-bold" style={{ color: '#0f172a' }}>See what Goal Getter can do</h2>
        <Row className="g-4 justify-content-center mt-2">
          <Col xs={12} md={4}>
            <div className="example-prompt-card p-4 h-100 shadow-sm text-start">
              <p className="mb-0 prompt-text">
              "I want to learn C++ this June. I am a high school junior new to coding, with just a little experience in Python. Can you sketch out a rough 4-week study plan?"
              </p>
            </div>
          </Col>
          <Col xs={12} md={4}>
            <div className="example-prompt-card p-4 h-100 shadow-sm text-start">
              <p className="mb-0 prompt-text">
              "I have a massive history research paper due on April 24th. Help me break down the milestones. Based on my free time that week, schedule the drafting and final review sessions on my calendar, and email me the milestone checklist."
              </p>
            </div>
          </Col>
          <Col xs={12} md={4}>
            <div className="example-prompt-card p-4 h-100 shadow-sm text-start">
              <p className="mb-0 prompt-text">
              "Draft a quick, exciting email inviting my friends to a weekend hackathon at my house next Saturday. Oh, and put a reminder on my calendar for Friday at 5 PM to order the food!"
              </p>
            </div>
          </Col>
        </Row>
      </Container>

      {/* Bottom Call To Action */}
      <Container fluid className="bottom-cta text-center">
        <h3>Ready to achieve more?</h3>
        <Button size="lg" className="cta-button mt-3" onClick={login}>Start Planning Now</Button>
      </Container>
    </div>
  )
}

export default Login