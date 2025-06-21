const express = require('express');
const fs = require('fs');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const { exec } = require('child_process');
const { RekognitionClient, CompareFacesCommand } = require('@aws-sdk/client-rekognition');
require('dotenv').config();

const app = express();
app.use(express.json({ limit: '10mb' })); // Increase size limit for image uploads

// Environment variables
const JWT_SECRET = process.env.JWT_SECRET;
const AWS_REGION = process.env.AWS_REGION;
const AWS_ACCESS_KEY = process.env.AWS_ACCESS_KEY;
const AWS_SECRET_KEY = process.env.AWS_SECRET_KEY;

// AWS Rekognition client configuration
const rekognition = new RekognitionClient({
    region: AWS_REGION,
    credentials: {
        accessKeyId: AWS_ACCESS_KEY,
        secretAccessKey: AWS_SECRET_KEY,
    },
});

// Temporary user storage
const users = {};

// Home route
app.get('/', (req, res) => {
    res.send('Server is up and running!');
});

// User registration
app.post('/register', async (req, res) => {
    const { username, password } = req.body;

    if (users[username]) {
        return res.status(400).json({ error: 'User already exists!' });
    }

    const hashedPassword = await bcrypt.hash(password, 10);
    users[username] = { password: hashedPassword };
    res.json({ message: 'User registered successfully!' });
});

// User login
app.post('/login', async (req, res) => {
    const { username, password } = req.body;
    const user = users[username];

    if (!user || !(await bcrypt.compare(password, user.password))) {
        return res.status(401).json({ error: 'Invalid credentials' });
    }

    const token = jwt.sign({ username }, JWT_SECRET, { expiresIn: '1h' });
    res.json({ token });
});

// Middleware to authenticate JWT tokens
const authenticateToken = (req, res, next) => {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];
    if (!token) return res.status(401).json({ error: 'Access denied' });

    jwt.verify(token, JWT_SECRET, (err, user) => {
        if (err) return res.status(403).json({ error: 'Invalid token' });
        req.user = user;
        next();
    });
};

// Liveness Detection + Attendance Logging
app.post('/log-attendance', authenticateToken, (req, res) => {
    exec('python liveness_detection.py', async (error, stdout, stderr) => {
        if (error) {
            console.error('Liveness detection error:', error);
            return res.status(500).json({ error: 'Liveness detection failed', details: error.message });
        }

        if (!stdout.trim().includes('Liveness confirmed')) {
            return res.status(400).json({ error: 'Liveness check failed' });
        }

        console.log('Liveness confirmed:', stdout.trim());

        const { image } = req.body; // Base64 image data
        const referenceImagePath = "C:/Users/HP/Desktop/facial-recognition-backend/ruthvik.jpg";

        let referenceImage;
        try {
            referenceImage = fs.readFileSync(referenceImagePath);
        } catch (fileError) {
            console.error("Error reading reference image:", fileError);
            return res.status(500).json({ error: "Failed to read reference image", details: fileError.message });
        }

        // Defensive checks
        if (!image || Buffer.from(image, 'base64').length === 0) {
            console.error("Source image is undefined or invalid!");
            return res.status(400).json({ error: "Invalid source image" });
        }
        if (!referenceImage || referenceImage.length === 0) {
            console.error("Reference image is undefined or invalid!");
            return res.status(400).json({ error: "Invalid reference image" });
        }

        // Debug logs
        console.log("Source Image Bytes Length:", Buffer.from(image, 'base64').length);
        console.log("Reference Image Bytes Length:", referenceImage.length);

        const params = {
            SourceImage: { Bytes: Buffer.from(image, 'base64') },
            TargetImage: { Bytes: referenceImage }
        };

        try {
            const command = new CompareFacesCommand(params);
            const rekognitionResult = await rekognition.send(command);

            if (!rekognitionResult.FaceMatches || rekognitionResult.FaceMatches.length === 0) {
                return res.status(400).json({ error: 'Face not recognized' });
            }

            const { username } = req.user;
            const timestamp = new Date();
            const logEntry = {
                timestamp,
                username,
                liveness_result: stdout.trim(),
                recognitionDetails: rekognitionResult.FaceMatches,
            };

            fs.appendFileSync('attendance_logs.json', JSON.stringify(logEntry) + '\n');

            res.json({
                message: `Attendance logged successfully for ${username}`,
                timestamp,
                recognitionDetails: rekognitionResult.FaceMatches,
            });
        } catch (rekognitionError) {
            console.error('AWS Rekognition error:', rekognitionError);
            res.status(500).json({ error: 'AWS Rekognition failed', details: rekognitionError.message });
        }
    });
});

// Start server
const PORT = 3000;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
