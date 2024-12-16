// Open the notification in fullscreen when clicked
function openNotification(notificationElement) {
    // Get the data of the clicked notification
    var notificationId = notificationElement.getAttribute('data-id');
    var title = notificationElement.querySelector('h4').innerText;
    var details = "Detailed information about notification " + notificationId + " goes here. This can be dynamically loaded based on the notification.";

    // Update modal content
    document.getElementById('modalTitle').innerText = title;
    document.getElementById('modalDetails').innerText = details;

    // Show the modal
    document.getElementById('notificationModal').style.display = 'block';
}

// Close the modal when the close button is clicked
function closeModal() {
    document.getElementById('notificationModal').style.display = 'none';
}
