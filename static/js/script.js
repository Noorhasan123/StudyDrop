/* =================================
   STUDYDROP - MAIN JAVASCRIPT
================================= */


/* =================================
   COPY TEXT
================================= */

function copyText(text) {

    navigator.clipboard.writeText(text)
        .then(function () {

            showCopyMessage();

        })
        .catch(function () {

            alert("Could not copy.");

        });
}


/* =================================
   COPY SUCCESS MESSAGE
================================= */

function showCopyMessage() {

    const oldMessage =
        document.querySelector(".copy-message");

    if (oldMessage) {
        oldMessage.remove();
    }


    const message =
        document.createElement("div");

    message.className =
        "copy-message";

    message.textContent =
        "Copied successfully ✓";


    document.body.appendChild(message);


    setTimeout(function () {

        message.classList.add("show");

    }, 10);


    setTimeout(function () {

        message.classList.remove("show");

        setTimeout(function () {
            message.remove();
        }, 200);

    }, 1600);
}


/* =================================
   ROOM EXPIRY COUNTDOWN
================================= */

const expiryElement =
    document.getElementById("room-expiry");


if (expiryElement) {

    const expiryTime =
        new Date(
            expiryElement.dataset.expiry
        ).getTime();


    function updateCountdown() {

        const countdown =
            document.getElementById("countdown");


        if (!countdown) {
            return;
        }


        const now =
            new Date().getTime();


        const difference =
            expiryTime - now;


        if (difference <= 0) {

            countdown.innerHTML =
                "Expired";


            setTimeout(function () {

                location.reload();

            }, 1000);


            return;
        }


        const hours =
            Math.floor(
                difference /
                (1000 * 60 * 60)
            );


        const minutes =
            Math.floor(
                (difference %
                (1000 * 60 * 60)) /
                (1000 * 60)
            );


        const seconds =
            Math.floor(
                (difference %
                (1000 * 60)) /
                1000
            );


        countdown.innerHTML =
            hours + "h " +
            minutes + "m " +
            seconds + "s";
    }


    updateCountdown();


    setInterval(
        updateCountdown,
        1000
    );
}