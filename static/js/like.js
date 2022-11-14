function changeText(comment_id){
    let specified_button = document.getElementById(`button_marker${comment_id}`);
    if (specified_button.className == "icon fa-thumbs-up"){
        var request = new XMLHttpRequest();
        request.open("GET","/like_comment/"+comment_id,true);
        request.send();
        specified_button.className = "icon solid fa-thumbs-up";
        specified_button.style.color="#F2A900"
        let counter = document.getElementById(`like_counter${comment_id}`);
        let text = counter.innerHTML;
        var like_number = parseInt(text.split(" ")[1]);
        like_number+=1
        counter.innerHTML = `+ ${like_number} likes`
    }else{
        var request = new XMLHttpRequest();
        request.open("GET","/unlike_comment/"+comment_id,true);
        request.send();
        specified_button.className = "icon fa-thumbs-up";
        specified_button.style.color="white"
        let counter = document.getElementById(`like_counter${comment_id}`);
        let text = counter.innerHTML;
        var like_number = parseInt(text.split(" ")[1]);
        like_number-=1
        counter.innerHTML = `+ ${like_number} likes`
    }
}
const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]')
const popoverList = [...popoverTriggerList].map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl))
const popover = new bootstrap.Popover('.popover-dismiss', {
  trigger: 'focus'
})