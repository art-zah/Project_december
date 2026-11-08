function closeNotification() {
    const notification = document.getElementById("notification");

    if (notification) {notification.classList.add("notification-hide"); setTimeout(() => notification.remove(), 400)}}

document.addEventListener("DOMContentLoaded", () => {
    const notification = document.getElementById("notification");

    if (notification) {setTimeout(closeNotification, 5000)}});