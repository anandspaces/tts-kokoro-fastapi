const container = document.getElementById('canvas-container');
const languageSelect = document.getElementById('language-select');
const textInput = document.getElementById('text-input');
const speakBtn = document.getElementById('speak-btn');

// --- Audio Context ---
let audioCtx;
let analyser;
let dataArray;
let source;

async function initAudio() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 512;
        dataArray = new Uint8Array(analyser.frequencyBinCount);
    }
    if (audioCtx.state === 'suspended') {
        await audioCtx.resume();
    }
}

async function playAudio(audioBlob) {
    await initAudio();

    if (source) {
        source.stop();
    }

    const arrayBuffer = await audioBlob.arrayBuffer();
    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

    source = audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(analyser);
    analyser.connect(audioCtx.destination);
    source.start(0);
}

// --- Three.js ---
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });

renderer.setSize(window.innerWidth, window.innerHeight);
container.appendChild(renderer.domElement);

// Lights
const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
scene.add(ambientLight);

const pointLight = new THREE.PointLight(0xffffff, 1);
pointLight.position.set(5, 5, 5);
scene.add(pointLight);

// Sphere
const geometry = new THREE.IcosahedronGeometry(1.5, 4); // Radius 1.5, Detail 4
const material = new THREE.MeshStandardMaterial({
    color: 0xbb86fc,
    wireframe: true,
    roughness: 0.4,
    metalness: 0.8
});
const sphere = new THREE.Mesh(geometry, material);
scene.add(sphere);

camera.position.z = 5;

// Original vertices storage for animation reference
const originalPositions = geometry.attributes.position.array.slice();

// Animation Loop
const clock = new THREE.Clock();

function animate() {
    requestAnimationFrame(animate);

    const time = clock.getElapsedTime();

    // Default idle rotation
    sphere.rotation.y += 0.002;
    sphere.rotation.x += 0.001;

    if (analyser) {
        analyser.getByteFrequencyData(dataArray);

        // Calculate average frequency for scaling/color
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
        }
        const average = sum / dataArray.length;

        // Deform sphere based on frequency
        const positions = geometry.attributes.position.array;

        // We will map low freq to general shape, high freq to spikes?
        // Let's just do a noise-like displacement based on vertex index + freq

        // A simple bass kick effect on scale
        const scale = 1 + (average / 256) * 0.3;
        sphere.scale.set(scale, scale, scale);

        // Color shift based on intensity
        const hue = (0.7 + (average / 256) * 0.2) % 1; // Purple to Blue-ish
        material.color.setHSL(hue, 0.8, 0.5);

        // Vertex displacement
        // Accessing frequencies from dataArray. 
        // We have 256 bins.
        for (let i = 0; i < positions.length; i += 3) {
            // Map vertex index to frequency bin
            const binIndex = i % dataArray.length;
            const freq = dataArray[binIndex];

            // Direction vector
            const vx = originalPositions[i];
            const vy = originalPositions[i + 1];
            const vz = originalPositions[i + 2];

            // Normalize roughly (it's a sphere so positions are effectively normals)
            const mag = Math.sqrt(vx * vx + vy * vy + vz * vz);
            const nx = vx / mag;
            const ny = vy / mag;
            const nz = vz / mag;

            // Displacement amount
            const displacement = (freq / 255) * 0.5; // Max 0.5 units out

            // Apply
            positions[i] = originalPositions[i] + nx * displacement;
            positions[i + 1] = originalPositions[i + 1] + ny * displacement;
            positions[i + 2] = originalPositions[i + 2] + nz * displacement;
        }

        geometry.attributes.position.needsUpdate = true;
    }

    renderer.render(scene, camera);
}

animate();

// Resize handler
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

// --- API Interaction ---
async function fetchLanguages() {
    try {
        const response = await fetch('/languages');
        const data = await response.json();

        languageSelect.innerHTML = '<option value="" disabled selected>Select Language</option>';
        data.languages.forEach(lang => {
            const option = document.createElement('option');
            option.value = lang;
            option.textContent = lang.charAt(0).toUpperCase() + lang.slice(1);
            languageSelect.appendChild(option);
        });
    } catch (e) {
        console.error("Failed to load languages", e);
        languageSelect.innerHTML = '<option disabled>Error loading languages</option>';
    }
}

speakBtn.addEventListener('click', async () => {
    const text = textInput.value.trim();
    const lang = languageSelect.value;

    if (!text || !lang) {
        alert("Please enter text and select a language.");
        return;
    }

    speakBtn.disabled = true;
    speakBtn.innerHTML = '<span>Synthesizing...</span><div class="btn-bg"></div>';

    try {
        const response = await fetch('/synthesize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text, language: lang })
        });

        if (!response.ok) {
            throw new Error('Synthesis failed');
        }

        const blob = await response.blob();
        await playAudio(blob);

    } catch (e) {
        console.error(e);
        alert("Error synthesizing audio.");
    } finally {
        speakBtn.disabled = false;
        speakBtn.innerHTML = '<span>Synthesize</span><div class="btn-bg"></div>';
    }
});

// Init
fetchLanguages();
