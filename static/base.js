document.addEventListener('DOMContentLoaded', () => {
  import('https://unpkg.com/threejs-toys@0.0.8/build/threejs-toys.module.cdn.min.js')
    .then(module => {
      const { neonCursor } = module;
      neonCursor({
        el: document.getElementById('app'),
        shaderPoints: 16,
        curvePoints: 80,
        curveLerp: 0.5,
        radius1: 5,
        radius2: 30,
        velocityTreshold: 10,
        sleepRadiusX: 100,
        sleepRadiusY: 100,
        sleepTimeCoefX: 0.0025,
        sleepTimeCoefY: 0.0025
      });
    })
    .catch(err => {
      console.error('Error loading module:', err);
    });
});
window.addEventListener("load", function () {
  const loader = document.getElementById("loading-screen");
  loader.style.opacity = "0";
  setTimeout(() => {
      loader.style.display = "none";
      document.body.classList.remove("loading");
  }, 500); // fade out after 0.5s
});
const menuToggle = document.querySelector('.menu-toggle');
const menu = document.querySelector('.menu');

fetch('http://192.168.1.17:5000/ask', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ message: 'What is your opening time?' })
})
  .then(response => response.json())
  .then(data => console.log(data.response));

