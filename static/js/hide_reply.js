function handleReplyVisibility(parent_id){
    var button = document.getElementById(`hide_reply${parent_id}`)
    var array_of_children = button.getAttribute("value").split(";");
    array_of_children = array_of_children.filter(item => item !== "")
    if (button.style.color == "rgb(242, 169, 0)"){
        button.style.color = "white";
        array_of_children.forEach(setVisibilityOn)
        document.getElementById(`reply_text${parent_id}`).innerHTML = "Hide Replies";
        button.className = "icon solid fa-eye"
    }else{
        button.style.color = "#F2A900";
        array_of_children.forEach(setVisibilityOff)
        setTimeout(changeText,150);
        function changeText(){
            document.getElementById(`reply_text${parent_id}`).innerHTML = "Show Replies";
            button.className = "icon solid fa-eye-slash"
        }
    }
}
function setVisibilityOn(comment_id){
    var button = document.getElementById(`hide_reply${comment_id}`)
    button.style.color = "white";
    button.className = "icon solid fa-eye"
    document.getElementById(`reply_text${comment_id}`).innerHTML = "Hide Replies";
    var div = document.getElementById(`visibility_tag_${comment_id}`)
    div.style.display = "block";
    div.className = "visible";
}
function setVisibilityOff(comment_id){
    var div = document.getElementById(`visibility_tag_${comment_id}`)
    div.className = "hidden";
    setTimeout(setDisplayOff,200);
    function setDisplayOff(){
        div.style.display = "none";
    }
}